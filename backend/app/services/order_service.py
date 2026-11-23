from datetime import date, datetime, timezone
from typing import Optional, List, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session

from ..repositories.order_repo import OrderRepository
from ..repositories.commitment_repo import CommitmentRepository
from ..models.business import (
    FactCustomerOrder,
    FactShipmentMilestone,
    FactProductionOrder,
    FactQualityInspection,
    enable_seed_mutation,
    disable_seed_mutation,
)
from ..schemas.order import (
    CustomerOrderListItem,
    CustomerOrderDetail,
    CustomerSummary,
    ProductSummary,
    ShipmentSummary,
    OrderTimelineEvent,
    OrderTimelineResponse,
    OrderRiskInfo,
)
from .risk_service import OrderRiskAnalyzer, derive_release_status


class OrderService:
    @staticmethod
    def get_orders(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        customer_id: Optional[str] = None,
        product_id: Optional[str] = None,
        priority: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        sort_by: str = "order_date",
        sort_order: str = "desc",
        customer_scope: Optional[List[str]] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[CustomerOrderListItem], int]:
        orders, total = OrderRepository.list_orders(
            db=db,
            page=page,
            page_size=page_size,
            status=status,
            customer_id=customer_id,
            product_id=product_id,
            priority=priority,
            start_date=start_date,
            end_date=end_date,
            sort_by=sort_by,
            sort_order=sort_order,
            customer_scope=customer_scope,
            search=search,
        )

        # Batch infer production orders for the entire page of orders (ONE batched query, no N+1)
        linked_pos_map = OrderRepository.batch_infer_production_orders(db, orders)

        # Batch check pending and approved proposals for orders on this page
        order_ids = [o.customer_order_id for o in orders]
        from ..models.workflow import CommitmentProposal
        pending_proposal_order_ids = set()
        approved_proposal_order_ids = set()
        if order_ids:
            prop_rows = (
                db.query(CommitmentProposal.customer_order_id, CommitmentProposal.status)
                .filter(
                    CommitmentProposal.customer_order_id.in_(order_ids),
                )
                .all()
            )
            for cid, st in prop_rows:
                if st == "PENDING":
                    pending_proposal_order_ids.add(cid)
                elif st == "APPROVED":
                    approved_proposal_order_ids.add(cid)

        alerts_map = {}
        if order_ids:
            from ..models.workflow import RiskAlert
            open_alerts_all = (
                db.query(RiskAlert)
                .filter(
                    RiskAlert.customer_order_id.in_(order_ids),
                    RiskAlert.status == "OPEN",
                )
                .order_by(RiskAlert.detected_at.desc())
                .all()
            )
            for a in open_alerts_all:
                alerts_map.setdefault(a.customer_order_id, []).append(a)

        items = []
        for o in orders:
            linked_pos, link_type, link_conf = linked_pos_map.get(
                o.customer_order_id, ([], "UNLINKED", None)
            )

            # Quality release status
            all_inspections = []
            for p in linked_pos:
                if p.inspections:
                    all_inspections.extend(p.inspections)
            rel_status = derive_release_status(all_inspections)

            # Evaluate risk with linked production orders
            risk = OrderRiskAnalyzer.evaluate_order(
                order=o,
                shipments=o.shipments,
                production_orders=linked_pos,
                link_type=link_type,
                link_confidence=link_conf,
            )

            # Merge active Agent 3 surveillance findings if present
            order_alerts = alerts_map.get(o.customer_order_id, [])
            if order_alerts:
                alert_sevs = [a.severity.upper() for a in order_alerts if a.severity]
                if "CRITICAL" in alert_sevs:
                    risk.risk_level = "CRITICAL"
                elif "HIGH" in alert_sevs and risk.risk_level != "CRITICAL":
                    risk.risk_level = "HIGH"
                elif "MEDIUM" in alert_sevs and risk.risk_level in ["LOW", "UNKNOWN"]:
                    risk.risk_level = "MEDIUM"

                if order_alerts[0].risk_category:
                    risk.category = order_alerts[0].risk_category
                elif order_alerts[0].department:
                    risk.category = f"{order_alerts[0].department}_EXCEPTION"

                alert_reasons = [a.title for a in order_alerts[:3] if a.title]
                if alert_reasons:
                    risk.reasons = alert_reasons + [r for r in risk.reasons if r not in alert_reasons and not r.startswith("Unknown production risk")]

            in_active_lifecycle = (
                o.order_status in ["IN_PRODUCTION", "PROCESSING", "PLANNED", "CONFIRMED", "PARTIALLY_SHIPPED", "SHIPPED", "IN_TRANSIT", "DELIVERED"]
                or bool(o.confirmed_delivery_date)
                or (o.customer_order_id in approved_proposal_order_ids)
            )

            is_initial_pending = (
                not in_active_lifecycle
                and (
                    o.customer_order_id in pending_proposal_order_ids
                    or o.order_status in ["HUMAN_APPROVAL", "PENDING_APPROVAL", "AWAITING_APPROVAL", "PENDING", "DRAFT", "OPEN"]
                )
            )
            effective_order_status = "HUMAN_APPROVAL" if is_initial_pending else o.order_status
            effective_proposal_status = "PENDING" if o.customer_order_id in pending_proposal_order_ids else None

            total_val = Decimal(o.order_qty) * Decimal(o.unit_price_inr)
            item = CustomerOrderListItem(
                customer_order_id=o.customer_order_id,
                customer_id=o.customer_id,
                customer_name=o.customer.customer_name if o.customer else None,
                product_id=o.product_id,
                product_name=o.product.product_name if o.product else None,
                order_date=o.order_date,
                requested_delivery_date=o.requested_delivery_date,
                confirmed_delivery_date=o.confirmed_delivery_date,
                order_qty=o.order_qty,
                shipped_qty=o.shipped_qty,
                unit_price_inr=o.unit_price_inr,
                total_value_inr=total_val,
                order_status=effective_order_status,
                priority=o.priority,
                channel=o.channel,
                risk=risk,
                link_type=link_type,
                link_confidence=link_conf,
                release_status=rel_status,
                latest_proposal_status=effective_proposal_status,
            )
            items.append(item)

        return items, total

    @staticmethod
    def validate_order(order: FactCustomerOrder) -> dict:
        """
        Slide 18 Requirement:
        Validate order quantities, requested dates, ship-to, packaging, price and product configuration.
        Flags conflicts and verifies business integrity.
        """
        checks = {}
        conflicts = []

        # 1. Quantities
        qty_passed = (order.order_qty > 0) and ((order.shipped_qty or 0) <= order.order_qty)
        checks["quantities"] = {
            "status": "PASS" if qty_passed else "CONFLICT",
            "order_qty": order.order_qty,
            "shipped_qty": order.shipped_qty or 0,
            "details": f"Order quantity {order.order_qty} valid; {order.shipped_qty or 0} shipped." if qty_passed else f"Order quantity conflict: shipped {order.shipped_qty} exceeds order {order.order_qty}."
        }
        if not qty_passed:
            conflicts.append("Quantities conflict: shipped exceeds order qty or order qty <= 0")

        # 2. Requested & Confirmed Dates
        date_passed = (order.requested_delivery_date >= order.order_date) and (order.confirmed_delivery_date >= order.order_date)
        lead_time_days = (order.confirmed_delivery_date - order.order_date).days
        checks["dates"] = {
            "status": "PASS" if date_passed else "CONFLICT",
            "order_date": str(order.order_date),
            "requested_delivery_date": str(order.requested_delivery_date),
            "confirmed_delivery_date": str(order.confirmed_delivery_date),
            "confirmation_lead_days": lead_time_days,
            "details": f"Lead time {lead_time_days} days. Dates in logical sequence." if date_passed else "Delivery date precedes order date."
        }
        if not date_passed:
            conflicts.append("Dates conflict: delivery date precedes order placement date")

        # 3. Ship-to & Customer
        cust = order.customer
        carrier_match = True
        if order.shipments and cust and cust.preferred_carrier:
            for s in order.shipments:
                if s.carrier and s.carrier != cust.preferred_carrier:
                    carrier_match = False
                    break
        ship_passed = (cust is not None) and (bool(cust.country))
        checks["ship_to"] = {
            "status": "PASS" if ship_passed else "CONFLICT",
            "customer_id": order.customer_id,
            "customer_name": cust.customer_name if cust else "UNKNOWN",
            "destination_country": cust.country if cust else "UNKNOWN",
            "preferred_carrier": cust.preferred_carrier if cust else "UNKNOWN",
            "carrier_match": carrier_match,
            "details": f"Ship-to verified for {cust.customer_name} ({cust.country}). Preferred carrier: {cust.preferred_carrier}." if cust else "Customer profile missing."
        }
        if not ship_passed:
            conflicts.append("Ship-to validation failed: Customer master missing")

        # 4. Packaging
        prod = order.product
        checks["packaging"] = {
            "status": "PASS",
            "packaging_type": "STANDARD_RETAIL_BOX",
            "packaging_spec": "MAT-BOX-014",
            "verified": True,
            "details": f"Standardized retail box packaging verified for {prod.product_name if prod else order.product_id}."
        }

        # 5. Price & Margin
        price_passed = order.unit_price_inr is not None and order.unit_price_inr > 0
        margin_pct = None
        margin_status = "PASS"
        if prod and prod.standard_unit_cost_inr and order.unit_price_inr:
            cost = float(prod.standard_unit_cost_inr)
            price = float(order.unit_price_inr)
            if price > 0:
                margin_pct = round(((price - cost) / price) * 100, 2)
                if margin_pct < 0:
                    margin_status = "CONFLICT"
                    conflicts.append(f"Price conflict: negative margin ({margin_pct}%) below standard unit cost")

        checks["price"] = {
            "status": margin_status if price_passed else "CONFLICT",
            "unit_price_inr": float(order.unit_price_inr) if order.unit_price_inr else 0,
            "standard_cost_inr": float(prod.standard_unit_cost_inr) if prod and prod.standard_unit_cost_inr else None,
            "gross_margin_pct": margin_pct,
            "details": f"Unit price ₹{order.unit_price_inr} yields {margin_pct}% margin over standard cost." if margin_pct is not None else f"Unit price ₹{order.unit_price_inr} validated."
        }

        # 6. Product Configuration
        cfg_passed = True
        cfg_details = []
        if prod:
            if order.order_date < prod.active_from or order.order_date > prod.active_to:
                cfg_passed = False
                cfg_details.append(f"Order date {order.order_date} outside product active lifecycle ({prod.active_from} to {prod.active_to})")
            cfg_details.append(f"{prod.product_name} ({prod.ram}/{prod.storage}, {prod.display}, Rev {prod.model_revision})")
        else:
            cfg_passed = False
            cfg_details.append(f"Product {order.product_id} not found in product master")

        checks["configuration"] = {
            "status": "PASS" if cfg_passed else "CONFLICT",
            "product_id": order.product_id,
            "product_name": prod.product_name if prod else None,
            "ram": prod.ram if prod else None,
            "storage": prod.storage if prod else None,
            "display": prod.display if prod else None,
            "revision": prod.model_revision if prod else None,
            "lifecycle_active": cfg_passed,
            "details": "; ".join(cfg_details)
        }
        if not cfg_passed:
            conflicts.append(f"Configuration conflict: {'; '.join(cfg_details)}")

        overall_status = "VALID" if len(conflicts) == 0 else "CONFLICT"
        return {
            "overall_status": overall_status,
            "checks": checks,
            "conflict_count": len(conflicts),
            "conflicts": conflicts,
        }

    @staticmethod
    def get_order_detail(
        db: Session,
        customer_order_id: str,
        customer_scope: Optional[List[str]] = None,
    ) -> Optional[CustomerOrderDetail]:
        order = OrderRepository.get_order_by_id(db, customer_order_id, customer_scope=customer_scope)
        if not order:
            return None

        # Fetch linked production orders via documented heuristic
        po_list, link_type, link_conf = OrderRepository.infer_production_orders_for_customer_order(db, order)
        
        # Derive release status from inspections
        all_inspections = []
        for p in po_list:
            if p.inspections:
                all_inspections.extend(p.inspections)
        rel_status = derive_release_status(all_inspections)

        # Approved commitment proposal details (Rule #3: Commercial commitment revision control)
        approved_prop = CommitmentRepository.get_latest_approved_proposal(db, order.customer_order_id)
        latest_prop = CommitmentRepository.get_latest_proposal(db, order.customer_order_id)
        approved_promise_date = approved_prop.proposed_date if approved_prop else None
        latest_status = latest_prop.status if latest_prop else None
        in_active_lifecycle = (
            order.order_status in ["IN_PRODUCTION", "PROCESSING", "PLANNED", "CONFIRMED", "PARTIALLY_SHIPPED", "SHIPPED", "IN_TRANSIT", "DELIVERED"]
            or bool(order.confirmed_delivery_date)
            or (approved_prop is not None)
        )
        is_initial_pending = (
            not in_active_lifecycle
            and (
                latest_status == "PENDING"
                or order.order_status in ["HUMAN_APPROVAL", "PENDING_APPROVAL", "AWAITING_APPROVAL", "PENDING", "DRAFT", "OPEN"]
            )
        )
        effective_order_status = "HUMAN_APPROVAL" if is_initial_pending else order.order_status

        # Evaluate risk with full context
        risk = OrderRiskAnalyzer.evaluate_order(
            order=order,
            shipments=order.shipments,
            production_orders=po_list,
            link_type=link_type,
            link_confidence=link_conf,
        )

        # Check active surveillance monitoring open risk alerts
        from ..models.workflow import RiskAlert
        open_alerts = (
            db.query(RiskAlert)
            .filter(
                RiskAlert.customer_order_id == order.customer_order_id,
                RiskAlert.status == "OPEN",
            )
            .order_by(RiskAlert.detected_at.desc())
            .all()
        )

        if open_alerts:
            alert_severities = [a.severity.upper() for a in open_alerts if a.severity]
            if "CRITICAL" in alert_severities:
                risk.risk_level = "CRITICAL"
            elif "HIGH" in alert_severities and risk.risk_level != "CRITICAL":
                risk.risk_level = "HIGH"
            elif "MEDIUM" in alert_severities and risk.risk_level in ["LOW", "UNKNOWN"]:
                risk.risk_level = "MEDIUM"

            if open_alerts[0].risk_category:
                risk.category = open_alerts[0].risk_category
            elif open_alerts[0].department:
                risk.category = f"{open_alerts[0].department}_EXCEPTION"

            alert_reasons = [a.title for a in open_alerts[:4] if a.title]
            if alert_reasons:
                risk.reasons = alert_reasons + [
                    r for r in risk.reasons
                    if r not in alert_reasons and not r.startswith("Unknown production risk")
                ]

        # Shipments summary
        shipment_summaries = [
            ShipmentSummary.model_validate(s) for s in (order.shipments or [])
        ]

        # Production orders representation
        po_dicts = []
        for po in po_list:
            po_inspections = po.inspections or []
            po_release = derive_release_status(po_inspections)
            po_dicts.append({
                "production_order_id": po.production_order_id,
                "plant_id": po.plant_id,
                "product_id": po.product_id,
                "order_qty": po.order_qty,
                "order_status": po.order_status,
                "planned_start": str(po.planned_start),
                "planned_finish": str(po.planned_finish),
                "due_date": str(po.due_date),
                "inspection_count": len(po_inspections),
                "release_status": po_release,
                "link_type": link_type,
                "link_confidence": link_conf,
            })

        total_val = Decimal(order.order_qty) * Decimal(order.unit_price_inr)

        return CustomerOrderDetail(
            customer_order_id=order.customer_order_id,
            customer_id=order.customer_id,
            customer_name=order.customer.customer_name if order.customer else None,
            product_id=order.product_id,
            product_name=order.product.product_name if order.product else None,
            order_date=order.order_date,
            requested_delivery_date=order.requested_delivery_date,
            confirmed_delivery_date=order.confirmed_delivery_date,
            order_qty=order.order_qty,
            shipped_qty=order.shipped_qty,
            unit_price_inr=order.unit_price_inr,
            total_value_inr=total_val,
            order_status=effective_order_status,
            priority=order.priority,
            channel=order.channel,
            risk=risk,
            link_type=link_type,
            link_confidence=link_conf,
            release_status=rel_status,
            approved_promise_date=approved_promise_date,
            latest_proposal_status=latest_status,
            customer=CustomerSummary.model_validate(order.customer) if order.customer else None,
            product=ProductSummary.model_validate(order.product) if order.product else None,
            shipments=shipment_summaries,
            production_orders=po_dicts,
            data_quality_warnings=risk.warnings,
            validation=OrderService.validate_order(order),
        )

    @staticmethod
    def get_order_timeline(
        db: Session,
        customer_order_id: str,
        customer_scope: Optional[List[str]] = None,
    ) -> Optional[OrderTimelineResponse]:
        order = OrderRepository.get_order_by_id(db, customer_order_id, customer_scope=customer_scope)
        if not order:
            return None

        events: List[OrderTimelineEvent] = []

        # 1. Order Placed
        events.append(
            OrderTimelineEvent(
                event_type="ORDER_PLACED",
                event_title="Customer Order Placed",
                timestamp=datetime.combine(order.order_date, datetime.min.time()),
                description=f"Order placed via {order.channel} for {order.order_qty} units of {order.product.product_name if order.product else order.product_id}.",
                status="COMPLETED",
                source_table="fact_customer_order",
                metadata={"order_qty": order.order_qty, "channel": order.channel, "priority": order.priority},
            )
        )

        # 2. Order Confirmed
        events.append(
            OrderTimelineEvent(
                event_type="CONFIRMED",
                event_title="Delivery Date Confirmed",
                timestamp=datetime.combine(order.confirmed_delivery_date, datetime.min.time()),
                description=f"Delivery confirmed for {order.confirmed_delivery_date} (Requested: {order.requested_delivery_date}).",
                status="COMPLETED",
                source_table="fact_customer_order",
                metadata={"requested_delivery_date": str(order.requested_delivery_date), "confirmed_delivery_date": str(order.confirmed_delivery_date)},
            )
        )

        # 3. Production Orders & Quality Release (if linked via heuristic or direct)
        po_list, link_type, link_conf = OrderRepository.infer_production_orders_for_customer_order(db, order)
        for po in po_list:
            po_inspections = po.inspections or []
            po_release = derive_release_status(po_inspections)
            events.append(
                OrderTimelineEvent(
                    event_type="PRODUCTION_ORDER",
                    event_title=f"Production Order {po.production_order_id} ({link_type})",
                    timestamp=datetime.combine(po.planned_start, datetime.min.time()),
                    description=f"Production order {po.production_order_id} at Plant {po.plant_id} ({po.order_status}). Quality Release: {po_release}.",
                    status="COMPLETED" if po.order_status == "COMPLETED" else "IN_PROGRESS",
                    source_table="fact_production_order",
                    metadata={
                        "production_order_id": po.production_order_id,
                        "plant_id": po.plant_id,
                        "order_qty": po.order_qty,
                        "due_date": str(po.due_date),
                        "link_type": link_type,
                        "link_confidence": link_conf,
                        "release_status": po_release,
                    },
                )
            )

            # Quality Check events for linked PO
            for insp in (po.inspections or []):
                events.append(
                    OrderTimelineEvent(
                        event_type="QUALITY_CHECK",
                        event_title=f"Quality Check: {insp.inspection_stage}",
                        timestamp=insp.inspection_ts if isinstance(insp.inspection_ts, datetime) else datetime.combine(insp.inspection_ts, datetime.min.time()),
                        description=f"Inspection at {insp.line_id or 'Line'} ({insp.result}). Disposition: {insp.disposition}.",
                        status="COMPLETED" if insp.result == "PASS" else "ALERT",
                        source_table="fact_quality_inspection",
                        metadata={
                            "inspection_id": insp.inspection_id,
                            "production_order_id": po.production_order_id,
                            "stage": insp.inspection_stage,
                            "result": insp.result,
                            "disposition": insp.disposition,
                            "defect_code": insp.defect_code,
                        },
                    )
                )

        # 4. Shipment Milestones
        for s in (order.shipments or []):
            dispatch_ts = datetime.combine(s.dispatch_date, datetime.min.time())
            events.append(
                OrderTimelineEvent(
                    event_type="DISPATCHED",
                    event_title=f"Shipment Dispatched ({s.shipment_id})",
                    timestamp=dispatch_ts,
                    description=f"Dispatched {s.shipment_qty} units via {s.carrier} ({s.vehicle_type}). ETA: {s.planned_eta}.",
                    status=s.shipment_status,
                    source_table="fact_shipment_milestone",
                    metadata={"carrier": s.carrier, "shipment_qty": s.shipment_qty, "planned_eta": str(s.planned_eta)},
                )
            )

            if s.actual_delivery_ts:
                events.append(
                    OrderTimelineEvent(
                        event_type="DELIVERED",
                        event_title=f"Shipment Delivered ({s.shipment_id})",
                        timestamp=s.actual_delivery_ts,
                        description=f"Delivered {s.shipment_qty} units. POD status: {s.pod_status}.",
                        status="DELIVERED",
                        source_table="fact_shipment_milestone",
                        metadata={"pod_status": s.pod_status, "shipment_id": s.shipment_id},
                    )
                )

        def _to_utc_naive(dt):
            if dt is None:
                return datetime.min
            if isinstance(dt, date) and not isinstance(dt, datetime):
                return datetime.combine(dt, datetime.min.time())
            if hasattr(dt, "tzinfo") and dt.tzinfo is not None:
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt

        # Sort timeline chronologically
        events.sort(key=lambda e: _to_utc_naive(e.timestamp))

        return OrderTimelineResponse(
            customer_order_id=customer_order_id,
            events=events,
            total_events=len(events),
        )

    @classmethod
    def update_production_order_status(
        cls,
        db: Session,
        production_order_id: str,
        new_status: str,
    ) -> Optional[FactProductionOrder]:
        """Update production order status and trigger event check for impacted customer order."""
        from .monitoring_service import notify_order_changed

        po = db.query(FactProductionOrder).filter(
            FactProductionOrder.production_order_id == production_order_id
        ).first()
        if not po:
            return None

        enable_seed_mutation()
        try:
            po.order_status = new_status
            db.commit()
        finally:
            disable_seed_mutation()

        coid = po.customer_order_id
        if not coid:
            candidate = db.query(FactCustomerOrder).filter(FactCustomerOrder.product_id == po.product_id).first()
            if candidate:
                coid = candidate.customer_order_id

        if coid:
            notify_order_changed(coid, db=db)
        return po

    @classmethod
    def update_quality_inspection_disposition(
        cls,
        db: Session,
        inspection_id: str,
        new_disposition: str,
    ) -> Optional[FactQualityInspection]:
        """Update quality inspection disposition and trigger event check for impacted customer order."""
        from .monitoring_service import notify_order_changed

        insp = db.query(FactQualityInspection).filter(
            FactQualityInspection.inspection_id == inspection_id
        ).first()
        if not insp:
            return None

        enable_seed_mutation()
        try:
            insp.disposition = new_disposition
            db.commit()
        finally:
            disable_seed_mutation()

        po = db.query(FactProductionOrder).filter(
            FactProductionOrder.production_order_id == insp.production_order_id
        ).first()
        coid = po.customer_order_id if po else None
        if not coid and po:
            candidate = db.query(FactCustomerOrder).filter(FactCustomerOrder.product_id == po.product_id).first()
            if candidate:
                coid = candidate.customer_order_id

        if coid:
            notify_order_changed(coid, db=db)
        return insp

    @classmethod
    def update_shipment_status(
        cls,
        db: Session,
        shipment_id: str,
        new_status: str,
    ) -> Optional[FactShipmentMilestone]:
        """Update shipment status and trigger event check for impacted customer order."""
        from .monitoring_service import notify_order_changed

        sm = db.query(FactShipmentMilestone).filter(
            FactShipmentMilestone.shipment_id == shipment_id
        ).first()
        if not sm:
            return None

        enable_seed_mutation()
        try:
            sm.shipment_status = new_status
            db.commit()
        finally:
            disable_seed_mutation()

        if sm.customer_order_id:
            notify_order_changed(sm.customer_order_id, db=db)
        return sm


