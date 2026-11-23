from datetime import date, datetime
from app.services.risk_service import OrderRiskAnalyzer
from app.models.business import FactCustomerOrder, FactShipmentMilestone, FactProductionOrder


def test_order_risk_actual_delay():
    # Past confirmed delivery date and not delivered
    order = FactCustomerOrder(
        customer_order_id="CO-TEST-01",
        customer_id="CUS-001",
        product_id="PROD-01",
        order_date=date(2026, 8, 1),
        requested_delivery_date=date(2026, 8, 10),
        confirmed_delivery_date=date(2026, 8, 12),
        order_qty=100,
        shipped_qty=0,
        unit_price_inr=1000,
        order_status="IN_PRODUCTION",
        priority="HIGH",
        channel="DIRECT",
    )
    risk = OrderRiskAnalyzer.evaluate_order(
        order=order,
        shipments=[],
        production_orders=[],
        as_of_date=date(2026, 8, 20),
    )
    assert risk.category == "ACTUAL_DELAY"
    assert risk.risk_level in ("HIGH", "CRITICAL")
    assert any("Overdue delivery" in r for r in risk.reasons)


def test_order_risk_quantity_inconsistency():
    # Shipped quantity exceeds order quantity
    order = FactCustomerOrder(
        customer_order_id="CO-TEST-02",
        customer_id="CUS-001",
        product_id="PROD-01",
        order_date=date(2026, 8, 1),
        requested_delivery_date=date(2026, 8, 10),
        confirmed_delivery_date=date(2026, 8, 12),
        order_qty=100,
        shipped_qty=150,
        unit_price_inr=1000,
        order_status="PARTIALLY_SHIPPED",
        priority="MEDIUM",
        channel="DIRECT",
    )
    risk = OrderRiskAnalyzer.evaluate_order(
        order=order,
        shipments=[],
        production_orders=[],
        as_of_date=date(2026, 8, 5),
    )
    assert any("Quantity inconsistency" in r for r in risk.reasons)


def test_order_risk_missing_production_link():
    order = FactCustomerOrder(
        customer_order_id="CO-TEST-03",
        customer_id="CUS-001",
        product_id="PROD-01",
        order_date=date(2026, 8, 1),
        requested_delivery_date=date(2026, 8, 30),
        confirmed_delivery_date=date(2026, 8, 30),
        order_qty=100,
        shipped_qty=0,
        unit_price_inr=1000,
        order_status="IN_PRODUCTION",
        priority="MEDIUM",
        channel="DIRECT",
    )
    risk = OrderRiskAnalyzer.evaluate_order(
        order=order,
        shipments=[],
        production_orders=[],  # Missing link
        as_of_date=date(2026, 8, 5),
    )
    assert risk.category == "UNKNOWN_RISK"
    assert any("Missing production link" in w for w in risk.warnings)

