from datetime import date
from app.services.risk_service import OrderRiskAnalyzer, derive_release_status
from app.models.business import FactCustomerOrder, FactShipmentMilestone, FactProductionOrder, FactQualityInspection
from app.repositories.order_repo import OrderRepository


def test_heuristic_production_linkage(db_session):
    """Test heuristic links customer order to production order by product_id and due_date window."""
    order = db_session.query(FactCustomerOrder).filter(FactCustomerOrder.customer_order_id == "CO-000001").first()
    assert order is not None

    pos, link_type, confidence = OrderRepository.infer_production_orders_for_customer_order(db_session, order)
    assert link_type == "INFERRED"
    assert confidence in ("HIGH", "MEDIUM")
    assert len(pos) > 0
    # Every candidate must match the product
    for p in pos:
        assert p.product_id == order.product_id


def test_quality_release_status_derivation():
    """Test derive_release_status logic across all dispositions."""
    class MockInspection:
        def __init__(self, disp):
            self.disposition = disp

    # All RELEASE -> RELEASED
    assert derive_release_status([MockInspection("RELEASE"), MockInspection("RELEASE")]) == "RELEASED"
    # Any HOLD -> ON_HOLD
    assert derive_release_status([MockInspection("RELEASE"), MockInspection("HOLD")]) == "ON_HOLD"
    # Any REWORK without HOLD -> REWORK
    assert derive_release_status([MockInspection("RELEASE"), MockInspection("REWORK")]) == "REWORK"
    # Any SCRAP without HOLD/REWORK -> SCRAPPED
    assert derive_release_status([MockInspection("RELEASE"), MockInspection("SCRAP")]) == "SCRAPPED"
    # Empty -> NOT_INSPECTED
    assert derive_release_status([]) == "NOT_INSPECTED"


def test_delivered_shortfall_is_data_quality_warning():
    """Test delivered order with shipped < order is flagged as data quality warning, not ACTUAL_DELAY."""
    order = FactCustomerOrder(
        customer_order_id="CO-TEST-DELIV",
        customer_id="CUS-001",
        product_id="SPH-A15-256",
        order_date=date(2026, 8, 1),
        requested_delivery_date=date(2026, 8, 20),
        confirmed_delivery_date=date(2026, 8, 20),
        order_qty=500,
        shipped_qty=300,
        unit_price_inr=1000,
        order_status="DELIVERED",
        priority="MEDIUM",
        channel="DIRECT",
    )
    # Delivered shipment milestone on time
    shipment = FactShipmentMilestone(
        shipment_id="SH-TEST-1",
        customer_order_id="CO-TEST-DELIV",
        plant_id="PLANT-01",
        carrier="FAST_FREIGHT",
        shipment_qty=300,
        shipment_status="DELIVERED",
        dispatch_date=date(2026, 8, 10),
        actual_delivery_ts=date(2026, 8, 15),
    )
    risk = OrderRiskAnalyzer.evaluate_order(order=order, shipments=[shipment], production_orders=[], as_of_date=date(2026, 11, 11))
    assert risk.category == "ON_SCHEDULE"
    assert any("Data quality warning" in w for w in risk.warnings)

