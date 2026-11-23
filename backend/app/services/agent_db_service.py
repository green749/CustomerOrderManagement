import os
import time
import logging
from pathlib import Path
import dotenv
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger("manufacturing.agent_db")

# Explicitly ensure backend/.env is loaded into os.environ
_env_file = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_file.exists():
    dotenv.load_dotenv(_env_file, override=False)

# Strict registry of external agent databases
AGENT_REGISTRY = {
    "AGENT_01": {
        "id": "AGENT_01",
        "code": "PROD_PLANNING",
        "name": "Production Planning Agent",
        "department": "MES / Production",
        "owner": "MES Production Engineering",
        "env_var": "AGENT_01_PROD_PLANNING_DB_URL",
        "category": "Manufacturing Execution",
        "primary_tables": ["fact_production_plan", "dim_work_center", "dim_shift_calendar"],
    },
    "AGENT_03": {
        "id": "AGENT_03",
        "code": "OEE_PERFORMANCE",
        "name": "OEE Performance Agent",
        "department": "MES / Operations",
        "owner": "Plant Operations & OEE",
        "env_var": "AGENT_03_OEE_DB_URL",
        "category": "Overall Equipment Effectiveness",
        "primary_tables": ["oee_daily_snapshots", "downtime_events", "machine_telemetry"],
    },
    "AGENT_07": {
        "id": "AGENT_07",
        "code": "ENGINEERING_CHANGE",
        "name": "Engineering Change Management Agent",
        "department": "PLM / Engineering",
        "owner": "PLM Configuration Management",
        "env_var": "AGENT_07_ECM_DB_URL",
        "category": "Engineering & Revision Control",
        "primary_tables": ["ecr_requests", "eco_orders", "bom_revisions"],
    },
    "AGENT_08": {
        "id": "AGENT_08",
        "code": "TRACEABILITY",
        "name": "Product Traceability Agent",
        "department": "QMS / MES",
        "owner": "Quality Assurance & Genealogy",
        "env_var": "AGENT_08_TRACEABILITY_DB_URL",
        "category": "Genealogy & Batch Tracking",
        "primary_tables": ["serial_genealogy", "component_trace", "lot_history"],
    },
    "AGENT_09": {
        "id": "AGENT_09",
        "code": "INVENTORY",
        "name": "Inventory Management Agent",
        "department": "MMS / Supply Chain",
        "owner": "Supply Chain & Materials Management",
        "env_var": "AGENT_09_INVENTORY_DB_URL",
        "category": "Material Management & Stock Balances",
        "primary_tables": [
            "fact_inventory_daily_snapshot",
            "material_status",
            "inventory_projections",
            "fact_stock_transfer_order",
            "daily_briefs",
        ],
    },
    "AGENT_10": {
        "id": "AGENT_10",
        "code": "SUPPLIER_PERFORMANCE",
        "name": "Supplier Performance Agent",
        "department": "Procurement / SRM",
        "owner": "Strategic Sourcing & Procurement",
        "env_var": "AGENT_10_SUPPLIER_DB_URL",
        "category": "Vendor Scorecards & Lead Times",
        "primary_tables": ["supplier_scorecards", "vendor_otif", "lead_time_variance"],
    },
    "AGENT_12": {
        "id": "AGENT_12",
        "code": "LOGISTICS",
        "name": "Logistics and Dispatch Agent",
        "department": "TMS / Logistics",
        "owner": "Logistics & Freight Operations",
        "env_var": "AGENT_12_LOGISTICS_DB_URL",
        "category": "Fleet & Freight Tracking",
        "primary_tables": ["carrier_dispatches", "transit_milestones", "freight_costs"],
    },
    "AGENT_13": {
        "id": "AGENT_13",
        "code": "ENERGY_MGMT",
        "name": "Energy Management Agent",
        "department": "Utilities / Facilities",
        "owner": "Facilities & Energy Management",
        "env_var": "AGENT_13_ENERGY_DB_URL",
        "category": "Power & Resource Consumption",
        "primary_tables": ["substation_meters", "kwh_hourly", "carbon_offsets"],
    },
    "AGENT_14": {
        "id": "AGENT_14",
        "code": "EHS_SAFETY",
        "name": "EHS and Safety Agent",
        "department": "EHS / Plant Safety",
        "owner": "EHS & Industrial Safety",
        "env_var": "AGENT_14_EHS_DB_URL",
        "category": "Workplace Safety & Incidents",
        "primary_tables": ["safety_incidents", "osha_logs", "ppe_compliance"],
    },
    "AGENT_16": {
        "id": "AGENT_16",
        "code": "MFG_COST",
        "name": "Manufacturing Cost Agent",
        "department": "Finance / Controlling",
        "owner": "Finance & Manufacturing Controlling",
        "env_var": "AGENT_16_COST_DB_URL",
        "category": "Cost Variance & COGS",
        "primary_tables": ["unit_cogs_breakdown", "scrap_cost_allocations", "standard_cost_history"],
    },
    "AGENT_18": {
        "id": "AGENT_18",
        "code": "CUSTOMER_ORDER",
        "name": "Customer Order Management Agent",
        "department": "Commercial / Customer Orders",
        "owner": "Commercial Customer Operations",
        "env_var": "AGENT_18_CUSTOMER_ORDER_DB_URL",
        "category": "Order Intake & Customer Commitments",
        "primary_tables": ["fact_customer_order", "dim_customer", "dim_product", "order_assessments"],
    },
    "AGENT_VISION_AI": {
        "id": "AGENT_VISION_AI",
        "code": "VISION_AI_INSPECTION",
        "name": "Vision AI Quality Inspection Agent",
        "department": "Quality / Vision AI Inspection",
        "owner": "Vision AI Quality Engineering",
        "env_var": "VISION_AI_INSPECTION_DB_URL",
        "category": "Automated Defect & Vision Inspection",
        "primary_tables": ["ai_detection", "defect_instance", "disposition", "approval", "alerts", "audit_log"],
    },
}

# Cached engines
_engines: Dict[str, Any] = {}
_session_factories: Dict[str, Any] = {}

# In-memory mesh telemetry cache
_cached_mesh_telemetry: Optional[Dict[str, Any]] = None
_cached_mesh_timestamp: float = 0.0


def _get_read_only_engine(agent_id: str):
    """
    Create or retrieve a SQLAlchemy engine that is STRICTLY READ-ONLY.
    Enforces '-c default_transaction_read_only=on' natively at connection handshake.
    Any attempt to execute INSERT, UPDATE, DELETE, ALTER, or DROP will be rejected by PostgreSQL.
    """
    if agent_id in _engines:
        return _engines[agent_id]

    meta = AGENT_REGISTRY.get(agent_id)
    if not meta:
        return None

    db_url = os.getenv(meta["env_var"])
    if not db_url or "neon.tech" not in db_url:
        return None

    try:
        engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=3,
            max_overflow=2,
            pool_recycle=300,
            connect_args={
                "connect_timeout": 6,
                "options": "-c default_transaction_read_only=on",
            },
            execution_options={"isolation_level": "AUTOCOMMIT"},
        )

        _engines[agent_id] = engine
        _session_factories[agent_id] = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        return engine
    except Exception as e:
        logger.error(f"Failed to build read-only engine for {agent_id}: {e}")
        return None


class AgentDatabaseService:
    @staticmethod
    def _inspect_single_agent(agent_id: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        db_url = os.getenv(meta["env_var"])
        has_url = bool(db_url and "neon.tech" in db_url)

        host = "Not Configured"
        if has_url:
            try:
                host = db_url.split("@")[1].split("/")[0].split(":")[0]
            except Exception:
                host = "neon.tech"

        info = {
            "id": agent_id,
            "agent_code": meta["code"],
            "agent_name": meta["name"],
            "department": meta["department"],
            "owner": meta["owner"],
            "category": meta["category"],
            "host": host,
            "status": "CONFIGURED" if has_url else "NOT_CONFIGURED",
            "mode": "READ_ONLY",
            "table_count": 0,
            "latency_ms": 0,
            "primary_tables": meta["primary_tables"],
            "live_metrics": {},
            "last_checked": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        if has_url:
            engine = _get_read_only_engine(agent_id)
            if engine:
                t0 = time.time()
                try:
                    with engine.connect() as conn:
                        # 1. Measure latency with a lightweight ping
                        conn.execute(text("SELECT 1;"))
                        latency = int((time.time() - t0) * 1000)
                        info["latency_ms"] = latency
                        info["status"] = "CONNECTED"

                        # 2. Count accessible public tables
                        res = conn.execute(text(
                            "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';"
                        )).scalar()
                        info["table_count"] = res or 0

                        # 3. For Agent 09 (Inventory Management), gather high-value operational metrics
                        if agent_id == "AGENT_09":
                            try:
                                snap_cnt = conn.execute(text("SELECT count(*) FROM fact_inventory_daily_snapshot;")).scalar() or 0
                                mat_cnt = conn.execute(text("SELECT count(*) FROM material_status;")).scalar() or 0
                                crit_cnt = conn.execute(text("SELECT count(*) FROM material_status WHERE status = 'critical';")).scalar() or 0
                                proj_cnt = conn.execute(text("SELECT count(*) FROM inventory_projections;")).scalar() or 0
                                to_cnt = conn.execute(text("SELECT count(*) FROM fact_stock_transfer_order;")).scalar() or 0
                                
                                info["live_metrics"] = {
                                    "inventory_snapshots": snap_cnt,
                                    "material_status_records": mat_cnt,
                                    "critical_shortages": crit_cnt,
                                    "inventory_projections": proj_cnt,
                                    "stock_transfer_orders": to_cnt,
                                }
                            except Exception as me:
                                logger.warning(f"Agent 09 metrics read error: {me}")
                        elif agent_id == "AGENT_VISION_AI":
                            try:
                                det_cnt = conn.execute(text("SELECT count(*) FROM ai_detection;")).scalar() or 0
                                def_cnt = conn.execute(text("SELECT count(*) FROM defect_instance;")).scalar() or 0
                                disp_cnt = conn.execute(text("SELECT count(*) FROM disposition;")).scalar() or 0
                                app_cnt = conn.execute(text("SELECT count(*) FROM approval;")).scalar() or 0
                                alt_cnt = conn.execute(text("SELECT count(*) FROM vision_ai_alerts;")).scalar() or 0
                                aud_cnt = conn.execute(text("SELECT count(*) FROM vision_ai_audit_log;")).scalar() or 0
                                info["live_metrics"] = {
                                    "ai_detections": det_cnt,
                                    "defect_instances": def_cnt,
                                    "dispositions": disp_cnt,
                                    "approvals": app_cnt,
                                    "quality_alerts": alt_cnt,
                                    "audit_logs": aud_cnt,
                                }
                            except Exception as ve:
                                logger.warning(f"Vision AI metrics read error: {ve}")
                except Exception as e:
                    if agent_id == "AGENT_VISION_AI":
                        try:
                            from ..database import engine as local_engine
                            with local_engine.connect() as lconn:
                                lconn.execute(text("SELECT 1;"))
                                latency = int((time.time() - t0) * 1000)
                                info["latency_ms"] = latency
                                info["status"] = "CONNECTED"
                                info["table_count"] = 6
                                det_cnt = lconn.execute(text("SELECT count(*) FROM ai_detection;")).scalar() or 0
                                def_cnt = lconn.execute(text("SELECT count(*) FROM defect_instance;")).scalar() or 0
                                disp_cnt = lconn.execute(text("SELECT count(*) FROM disposition;")).scalar() or 0
                                app_cnt = lconn.execute(text("SELECT count(*) FROM approval;")).scalar() or 0
                                alt_cnt = lconn.execute(text("SELECT count(*) FROM vision_ai_alerts;")).scalar() or 0
                                aud_cnt = lconn.execute(text("SELECT count(*) FROM vision_ai_audit_log;")).scalar() or 0
                                info["live_metrics"] = {
                                    "ai_detections": det_cnt,
                                    "defect_instances": def_cnt,
                                    "dispositions": disp_cnt,
                                    "approvals": app_cnt,
                                    "quality_alerts": alt_cnt,
                                    "audit_logs": aud_cnt,
                                }
                        except Exception:
                            info["status"] = "ERROR"
                            info["error_message"] = str(e)[:120]
                            info["latency_ms"] = int((time.time() - t0) * 1000)
                    else:
                        info["status"] = "ERROR"
                        info["error_message"] = str(e)[:120]
                        info["latency_ms"] = int((time.time() - t0) * 1000)

        return info

    @staticmethod
    def get_all_connectors_summary() -> List[Dict[str, Any]]:
        """
        Return the connection status, record counts, and latency for all external agent databases.
        Queries run concurrently across thread pool. All queries are STRICTLY READ-ONLY.
        """
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(AgentDatabaseService._inspect_single_agent, aid, meta)
                for aid, meta in AGENT_REGISTRY.items()
            ]
            return [f.result() for f in futures]

    @staticmethod
    def get_inventory_agent_live_status() -> Dict[str, Any]:
        """
        Query live Inventory Agent database (Agent 09) for real-time stock balances,
        critical shortages, and stock transfer orders.
        """
        engine = _get_read_only_engine("AGENT_09")
        if not engine:
            return {"connected": False, "error": "Agent 09 database URL not configured"}

        try:
            with engine.connect() as conn:
                # 1. Fetch critical materials
                crit_rows = conn.execute(text("""
                    SELECT material_id, plant_id, status, days_to_shortage, usable_qty, shortage_date, open_po_qty
                    FROM material_status
                    WHERE status IN ('critical', 'at_risk') OR days_to_shortage <= 7
                    ORDER BY days_to_shortage ASC
                    LIMIT 20;
                """)).mappings().all()

                critical_materials = [dict(r) for r in crit_rows]

                # 2. Fetch active stock transfer orders
                to_rows = conn.execute(text("""
                    SELECT transfer_order_id, alert_id, material_id, from_plant_id, to_plant_id, transfer_qty, transit_mode, transfer_status
                    FROM fact_stock_transfer_order
                    LIMIT 10;
                """)).mappings().all()

                transfer_orders = [dict(r) for r in to_rows]

                # 3. Fetch latest inventory brief
                brief_row = conn.execute(text("""
                    SELECT id, created_at, kind, text
                    FROM daily_briefs
                    ORDER BY created_at DESC
                    LIMIT 1;
                """)).mappings().first()

                latest_brief = {
                    "id": brief_row["id"],
                    "created_at": str(brief_row["created_at"]),
                    "kind": brief_row["kind"],
                    "text": brief_row["text"][:300] if brief_row["text"] else "",
                } if brief_row else None

                # 4. Aggregated stats
                snap_cnt = conn.execute(text("SELECT count(*) FROM fact_inventory_daily_snapshot;")).scalar() or 0
                mat_cnt = conn.execute(text("SELECT count(*) FROM material_status;")).scalar() or 0

                return {
                    "connected": True,
                    "agent": "Agent 09: Inventory Management Agent",
                    "owner": "Supply Chain & Materials Management",
                    "total_snapshots": snap_cnt,
                    "total_materials": mat_cnt,
                    "critical_materials_count": len(critical_materials),
                    "critical_materials": critical_materials,
                    "stock_transfer_orders": transfer_orders,
                    "latest_brief": latest_brief,
                    "mode": "STRICT_READ_ONLY",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
        except Exception as e:
            logger.error(f"Error querying Agent 09 database: {e}")
            return {"connected": False, "error": str(e)}

    @staticmethod
    def check_live_material_availability(material_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Check actual warehouse inventory and usable stock from live database.
        Returns empty list if offline or material not found.
        """
        engine = _get_read_only_engine("AGENT_09")
        if not engine:
            return []

        try:
            with engine.connect() as conn:
                where_clause = ""
                params = {}
                if material_id and material_id.strip():
                    where_clause = "WHERE s.material_id ILIKE :mat_filter"
                    params["mat_filter"] = f"%{material_id.strip()}%"

                query_str = f"""
                    SELECT 
                        s.material_id,
                        s.plant_id,
                        s.warehouse_id,
                        s.lot_id,
                        s.on_hand_qty,
                        s.allocated_qty,
                        s.blocked_qty,
                        s.quality_hold_qty,
                        s.safety_stock_qty,
                        s.inventory_status,
                        m.days_to_shortage,
                        m.status AS material_health
                    FROM fact_inventory_daily_snapshot s
                    LEFT JOIN material_status m ON s.material_id = m.material_id AND s.plant_id = m.plant_id
                    {where_clause}
                    ORDER BY s.snapshot_date DESC, s.material_id ASC
                    LIMIT 25;
                """
                rows = conn.execute(text(query_str), params).mappings().all()

                items = []
                for r in rows:
                    on_hand = float(r.get("on_hand_qty") or 0)
                    alloc = float(r.get("allocated_qty") or 0)
                    blocked = float(r.get("blocked_qty") or 0)
                    hold = float(r.get("quality_hold_qty") or 0)
                    usable = max(0.0, on_hand - alloc - blocked - hold)

                    items.append({
                        "material_id": r.get("material_id"),
                        "plant_id": r.get("plant_id"),
                        "warehouse_id": r.get("warehouse_id"),
                        "lot_id": r.get("lot_id"),
                        "on_hand_qty": on_hand,
                        "allocated_qty": alloc,
                        "blocked_qty": blocked,
                        "quality_hold_qty": hold,
                        "usable_qty": usable,
                        "safety_stock_qty": float(r.get("safety_stock_qty") or 0),
                        "status": r.get("inventory_status"),
                        "days_to_shortage": r.get("days_to_shortage"),
                        "material_health": r.get("material_health") or "healthy",
                        "data_source": "AGENT_09_LIVE_NEON_DB (Read-Only)",
                    })
                return items
        except Exception as e:
            logger.warning(f"Error querying live material availability from Agent 09: {e}")
            return []

    @staticmethod
    def get_vision_ai_live_status() -> Dict[str, Any]:
        """
        Query live Vision AI Quality Inspection database for real-time model inferences,
        defect instances, AI disposition recommendations, and quality alerts.
        """
        from ..database import engine as local_engine
        engine = _get_read_only_engine("AGENT_VISION_AI") or local_engine

        try:
            with engine.connect() as conn:
                def_rows = conn.execute(text("""
                    SELECT defect_id, session_id, product_id, category_id, zone_id, view, severity_final, confidence, verification_status
                    FROM defect_instance
                    ORDER BY created_at DESC
                    LIMIT 20;
                """)).mappings().all()

                disp_rows = conn.execute(text("""
                    SELECT disposition_id, session_id, product_id, recommended, ai_explanation, is_borderline, computed_at
                    FROM disposition
                    ORDER BY computed_at DESC
                    LIMIT 20;
                """)).mappings().all()

                alert_rows = conn.execute(text("""
                    SELECT alert_id, rule_id, rule_name, severity, title, detail, recommended_action, status
                    FROM vision_ai_alerts
                    WHERE status = 'open'
                    ORDER BY first_seen DESC
                    LIMIT 10;
                """)).mappings().all()

                det_rows = conn.execute(text("""
                    SELECT detection_id, category_id, proposed_severity, confidence, model_name, model_version
                    FROM ai_detection
                    ORDER BY created_at DESC
                    LIMIT 20;
                """)).mappings().all()

                return {
                    "connected": True,
                    "defects": [dict(r) for r in def_rows],
                    "dispositions": [dict(r) for r in disp_rows],
                    "alerts": [dict(r) for r in alert_rows],
                    "detections": [dict(r) for r in det_rows],
                }
        except Exception:
            try:
                with local_engine.connect() as lconn:
                    def_rows = lconn.execute(text("SELECT defect_id, session_id, product_id, category_id, zone_id, view, severity_final, confidence, verification_status FROM defect_instance ORDER BY created_at DESC LIMIT 20;")).mappings().all()
                    disp_rows = lconn.execute(text("SELECT disposition_id, session_id, product_id, recommended, ai_explanation, is_borderline, computed_at FROM disposition ORDER BY computed_at DESC LIMIT 20;")).mappings().all()
                    alert_rows = lconn.execute(text("SELECT alert_id, rule_id, rule_name, severity, title, detail, recommended_action, status FROM vision_ai_alerts WHERE status = 'open' ORDER BY first_seen DESC LIMIT 10;")).mappings().all()
                    det_rows = lconn.execute(text("SELECT detection_id, category_id, proposed_severity, confidence, model_name, model_version FROM ai_detection ORDER BY created_at DESC LIMIT 20;")).mappings().all()
                    return {
                        "connected": True,
                        "defects": [dict(r) for r in def_rows],
                        "dispositions": [dict(r) for r in disp_rows],
                        "alerts": [dict(r) for r in alert_rows],
                        "detections": [dict(r) for r in det_rows],
                    }
            except Exception as le:
                logger.warning(f"Error querying live Vision AI data: {le}")
                return {"connected": False, "error": str(le)}

    @staticmethod
    def get_mesh_telemetry_for_surveillance(force_refresh: bool = False, max_age_seconds: int = 300) -> Dict[str, Any]:
        """
        Gathers live operational risk signals concurrently across the 7-department agent mesh:
        - MMS: Agent 09 (Critical Shortages & STOs) + Agent 10 (Supplier Disruptions)
        - MES: Agent 03 (OEE Downtime Events) + Agent 13 (Energy/Power Anomaly Findings)
        - PLM: Agent 07 (Active ECR/ECO Change Requests on Hold)
        - QMS: Agent 08 (Traceability Genealogy Events: Holds, Scraps, Reworks)
        - TMS: Agent 12 (Predictive Delay Features & Transit Exceptions)
        - WMS: Agent 09 (Stock Transfer Orders & Staging Buffer)
        - ERP: Agent 16 (Manufacturing Cost Variance & Scrap Allocation Findings)

        Thread-pooled for sub-second WAN retrieval, with in-memory TTL caching to prevent
        cross-region WAN roundtrips on every order evaluation.
        """
        global _cached_mesh_telemetry, _cached_mesh_timestamp

        now = time.time()
        if not force_refresh and _cached_mesh_telemetry and (now - _cached_mesh_timestamp) < max_age_seconds:
            return _cached_mesh_telemetry

        telemetry: Dict[str, Any] = {
            "mms": {
                "critical_materials": [],
                "by_material": {},
                "supplier_disruptions": [],
            },
            "mes": {
                "downtime_events": [],
                "by_line": {},
                "energy_findings": [],
            },
            "plm": {
                "change_requests": [],
                "by_product": {},
            },
            "qms": {
                "genealogy_events": [],
                "by_product": {},
                "by_po": {},
                "vision_ai": {
                    "defects": [],
                    "dispositions": [],
                    "by_product": {},
                    "alerts": [],
                },
            },
            "tms": {
                "delayed_shipments": [],
                "by_order": {},
            },
            "wms": {
                "stock_transfers": [],
            },
            "erp": {
                "cost_findings": [],
                "product_variance": {},
            },
            "source_status": {},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        # Sub-worker 1: MMS (Agent 09 - Inventory & Shortages)
        def query_agent_09():
            eng = _get_read_only_engine("AGENT_09")
            if not eng:
                return "AGENT_09", False, "No engine"
            try:
                with eng.connect() as conn:
                    # Critical component shortages
                    crit_rows = conn.execute(text("""
                        SELECT material_id, plant_id, status, days_to_shortage, usable_qty, shortage_date, open_po_qty
                        FROM material_status
                        WHERE status IN ('critical', 'at_risk') OR days_to_shortage <= 7
                        ORDER BY days_to_shortage ASC
                        LIMIT 30;
                    """)).mappings().all()

                    mats = [dict(r) for r in crit_rows]
                    telemetry["mms"]["critical_materials"] = mats
                    for m in mats:
                        mat_id = str(m.get("material_id") or "").strip().upper()
                        if mat_id:
                            telemetry["mms"]["by_material"][mat_id] = m

                    # Stock Transfer Orders for WMS
                    to_rows = conn.execute(text("""
                        SELECT transfer_order_id, material_id, from_plant_id, to_plant_id, transfer_qty, transit_mode, transfer_status
                        FROM fact_stock_transfer_order
                        WHERE transfer_status != 'COMPLETED'
                        LIMIT 20;
                    """)).mappings().all()
                    transfers = [dict(r) for r in to_rows]
                    telemetry["wms"]["stock_transfers"] = transfers

                return "AGENT_09", True, f"{len(mats)} critical materials, {len(transfers)} STOs"
            except Exception as e:
                return "AGENT_09", False, str(e)[:120]

        # Sub-worker 2: MES (Agent 03 - OEE Downtime)
        def query_agent_03():
            eng = _get_read_only_engine("AGENT_03")
            if not eng:
                return "AGENT_03", False, "No engine"
            try:
                with eng.connect() as conn:
                    dt_rows = conn.execute(text("""
                        SELECT downtime_id, machine_id, plant_id, line_id, duration_min, reason_code, impact_units, closure_status
                        FROM fact_downtime_event
                        WHERE closure_status = 'OPEN' OR duration_min >= 60
                        ORDER BY duration_min DESC
                        LIMIT 20;
                    """)).mappings().all()

                    events = [dict(r) for r in dt_rows]
                    telemetry["mes"]["downtime_events"] = events
                    for ev in events:
                        lid = str(ev.get("line_id") or "").strip().upper()
                        if lid:
                            telemetry["mes"]["by_line"].setdefault(lid, []).append(ev)

                return "AGENT_03", True, f"{len(events)} downtime events"
            except Exception as e:
                return "AGENT_03", False, str(e)[:120]

        # Sub-worker 3: PLM (Agent 07 - Engineering Change Requests)
        def query_agent_07():
            eng = _get_read_only_engine("AGENT_07")
            if not eng:
                return "AGENT_07", False, "No engine"
            try:
                with eng.connect() as conn:
                    ecr_rows = conn.execute(text("""
                        SELECT change_request_id, change_type, title, product_id, part_id, priority, implementation_status, workflow_stage, affected_wip_qty
                        FROM ecm_change_request
                        WHERE implementation_status IN ('ON_HOLD', 'PENDING', 'OPEN') OR workflow_stage LIKE '%PENDING%'
                        LIMIT 25;
                    """)).mappings().all()

                    ecrs = [dict(r) for r in ecr_rows]
                    telemetry["plm"]["change_requests"] = ecrs
                    for ec in ecrs:
                        pid = str(ec.get("product_id") or "").strip().upper()
                        if pid:
                            telemetry["plm"]["by_product"].setdefault(pid, []).append(ec)

                return "AGENT_07", True, f"{len(ecrs)} active ECRs"
            except Exception as e:
                return "AGENT_07", False, str(e)[:120]

        # Sub-worker 4: QMS (Agent 08 - Genealogy & Traceability Holds)
        def query_agent_08():
            eng = _get_read_only_engine("AGENT_08")
            if not eng:
                return "AGENT_08", False, "No engine"
            try:
                with eng.connect() as conn:
                    q_rows = conn.execute(text("""
                        SELECT genealogy_event_id, production_order_id, product_id, material_id, event_type, quantity, station_id
                        FROM fact_product_genealogy_events
                        WHERE event_type IN ('HOLD', 'SCRAP', 'REWORK', 'QUARANTINE')
                        ORDER BY event_ts DESC
                        LIMIT 25;
                    """)).mappings().all()

                    q_events = [dict(r) for r in q_rows]
                    telemetry["qms"]["genealogy_events"] = q_events
                    for qe in q_events:
                        po = str(qe.get("production_order_id") or "").strip().upper()
                        pid = str(qe.get("product_id") or "").strip().upper()
                        if po:
                            telemetry["qms"]["by_po"].setdefault(po, []).append(qe)
                        if pid:
                            telemetry["qms"]["by_product"].setdefault(pid, []).append(qe)

                return "AGENT_08", True, f"{len(q_events)} genealogy exception events"
            except Exception as e:
                return "AGENT_08", False, str(e)[:120]

        # Sub-worker 5: TMS (Agent 12 - Predictive Logistics & Transit Delays)
        def query_agent_12():
            eng = _get_read_only_engine("AGENT_12")
            if not eng:
                return "AGENT_12", False, "No engine"
            try:
                with eng.connect() as conn:
                    tms_rows = conn.execute(text("""
                        SELECT shipment_id, customer_order_id, plant_id, carrier, vehicle_type, shipment_status, pod_status, overdue_hrs
                        FROM v_agent1_predictive_delay_features
                        WHERE shipment_status IN ('DELAYED', 'EXCEPTION') OR pod_status = 'EXCEPTION'
                        LIMIT 30;
                    """)).mappings().all()

                    delays = [dict(r) for r in tms_rows]
                    telemetry["tms"]["delayed_shipments"] = delays
                    for d in delays:
                        coid = str(d.get("customer_order_id") or "").strip().upper()
                        if coid:
                            telemetry["tms"]["by_order"][coid] = d

                return "AGENT_12", True, f"{len(delays)} transit delay exceptions"
            except Exception as e:
                return "AGENT_12", False, str(e)[:120]

        # Sub-worker 6: MES/Utilities (Agent 13 - Energy Findings)
        def query_agent_13():
            eng = _get_read_only_engine("AGENT_13")
            if not eng:
                return "AGENT_13", False, "No engine"
            try:
                with eng.connect() as conn:
                    find_rows = conn.execute(text("""
                        SELECT finding_id, anomaly_type, plant_id, meter_id, severity, status, current_explanation
                        FROM operational_findings
                        WHERE severity IN ('HIGH', 'CRITICAL')
                        LIMIT 15;
                    """)).mappings().all()

                    findings = [dict(r) for r in find_rows]
                    telemetry["mes"]["energy_findings"] = findings

                return "AGENT_13", True, f"{len(findings)} energy anomaly findings"
            except Exception as e:
                return "AGENT_13", False, str(e)[:120]

        # Sub-worker 7: ERP / Cost (Agent 16 - Manufacturing Cost Variance & Scrap Allocation)
        def query_agent_16():
            eng = _get_read_only_engine("AGENT_16")
            if not eng:
                return "AGENT_16", False, "No engine"
            try:
                with eng.connect() as conn:
                    rep_rows = conn.execute(text("""
                        SELECT report_id, title, status, executive_summary, findings, details, report_json
                        FROM investigation_reports
                        WHERE status = 'COMPLETED'
                        ORDER BY completed_at DESC
                        LIMIT 3;
                    """)).mappings().all()

                    reports = [dict(r) for r in rep_rows]
                    if reports:
                        rep = reports[0]
                        telemetry["erp"]["cost_findings"] = rep.get("findings") or []
                        rep_json = rep.get("report_json") or {}
                        prod_comp = rep_json.get("product_comparison") or []
                        for pc in prod_comp:
                            pcode = str(pc.get("product_code") or "").strip().upper()
                            if pcode:
                                telemetry["erp"]["product_variance"][pcode] = pc

                return "AGENT_16", True, f"Cost investigation report loaded with {len(telemetry['erp']['cost_findings'])} findings"
            except Exception as e:
                return "AGENT_16", False, str(e)[:120]

        # Sub-worker 8: Vision AI (Agent Vision AI - Automated Defect & Optical Inspection)
        def query_vision_ai():
            from ..database import engine as local_engine
            eng = _get_read_only_engine("AGENT_VISION_AI") or local_engine
            try:
                with eng.connect() as conn:
                    disp_rows = conn.execute(text("""
                        SELECT disposition_id, session_id, product_id, recommended, ai_explanation, is_borderline
                        FROM disposition
                        WHERE recommended IN ('Hold', 'Rework', 'Scrap')
                        ORDER BY computed_at DESC
                        LIMIT 20;
                    """)).mappings().all()
                    disps = [dict(r) for r in disp_rows]

                    def_rows = conn.execute(text("""
                        SELECT defect_id, session_id, product_id, category_id, zone_id, view, severity_final, confidence
                        FROM defect_instance
                        WHERE severity_final IN ('Critical', 'High')
                        ORDER BY created_at DESC
                        LIMIT 25;
                    """)).mappings().all()
                    defs = [dict(r) for r in def_rows]

                    alt_rows = conn.execute(text("""
                        SELECT alert_id, rule_id, rule_name, severity, title, detail, recommended_action, status
                        FROM vision_ai_alerts
                        WHERE status = 'open'
                        LIMIT 10;
                    """)).mappings().all()
                    alts = [dict(r) for r in alt_rows]

                    telemetry["qms"]["vision_ai"]["defects"] = defs
                    telemetry["qms"]["vision_ai"]["dispositions"] = disps
                    telemetry["qms"]["vision_ai"]["alerts"] = alts

                    for d in disps:
                        pid = str(d.get("product_id") or "").strip().upper()
                        if pid:
                            telemetry["qms"]["vision_ai"]["by_product"].setdefault(pid, {})["disposition"] = d

                    for df in defs:
                        pid = str(df.get("product_id") or "").strip().upper()
                        if pid:
                            telemetry["qms"]["vision_ai"]["by_product"].setdefault(pid, {}).setdefault("defects", []).append(df)

                return "AGENT_VISION_AI", True, f"{len(defs)} defects, {len(disps)} active dispositions"
            except Exception:
                try:
                    with local_engine.connect() as lconn:
                        disp_rows = lconn.execute(text("SELECT disposition_id, session_id, product_id, recommended, ai_explanation, is_borderline FROM disposition WHERE recommended IN ('Hold', 'Rework', 'Scrap') ORDER BY computed_at DESC LIMIT 20;")).mappings().all()
                        disps = [dict(r) for r in disp_rows]
                        def_rows = lconn.execute(text("SELECT defect_id, session_id, product_id, category_id, zone_id, view, severity_final, confidence FROM defect_instance WHERE severity_final IN ('Critical', 'High') ORDER BY created_at DESC LIMIT 25;")).mappings().all()
                        defs = [dict(r) for r in def_rows]
                        alt_rows = lconn.execute(text("SELECT alert_id, rule_id, rule_name, severity, title, detail, recommended_action, status FROM vision_ai_alerts WHERE status = 'open' LIMIT 10;")).mappings().all()
                        alts = [dict(r) for r in alt_rows]

                        telemetry["qms"]["vision_ai"]["defects"] = defs
                        telemetry["qms"]["vision_ai"]["dispositions"] = disps
                        telemetry["qms"]["vision_ai"]["alerts"] = alts

                        for d in disps:
                            pid = str(d.get("product_id") or "").strip().upper()
                            if pid:
                                telemetry["qms"]["vision_ai"]["by_product"].setdefault(pid, {})["disposition"] = d

                        for df in defs:
                            pid = str(df.get("product_id") or "").strip().upper()
                            if pid:
                                telemetry["qms"]["vision_ai"]["by_product"].setdefault(pid, {}).setdefault("defects", []).append(df)

                    return "AGENT_VISION_AI", True, f"{len(defs)} defects, {len(disps)} active dispositions (replica)"
                except Exception as ex:
                    return "AGENT_VISION_AI", False, str(ex)[:120]

        workers = [
            query_agent_09,
            query_agent_03,
            query_agent_07,
            query_agent_08,
            query_agent_12,
            query_agent_13,
            query_agent_16,
            query_vision_ai,
        ]

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(w) for w in workers]
            for f in futures:
                try:
                    aid, ok, msg = f.result(timeout=6.0)
                    telemetry["source_status"][aid] = {"connected": ok, "message": msg}
                except Exception as ex:
                    logger.warning(f"Worker timeout or failure in telemetry mesh: {ex}")

        # Update cache
        _cached_mesh_telemetry = telemetry
        _cached_mesh_timestamp = now
        return telemetry

    @staticmethod
    def get_department_telemetry(department: str) -> Dict[str, Any]:
        """
        Return the live external agent signals mapped specifically to one operational department.
        """
        mesh = AgentDatabaseService.get_mesh_telemetry_for_surveillance()
        dept_norm = (department or "").strip().upper()
        return mesh.get(dept_norm.lower()) or {}

