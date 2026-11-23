import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.business import (
    FactCustomerOrder,
    FactProductionOrder,
    FactInventoryDailySnapshot,
    DimProduct,
    DimCustomer,
    DimPlant,
)
from app.services.promise_service import PromiseService


@pytest.fixture
def mock_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()

    # Seed minimal hand-built fixtures
    cust = DimCustomer(
        customer_id="CUS-001",
        customer_name="Global Devices",
        country="India",
        segment="Enterprise",
        service_level="OTIF-95",
        preferred_carrier="DHL",
    )
    cust2 = DimCustomer(
        customer_id="CUS-002",
        customer_name="Nexus Retail",
        country="India",
        segment="Retail",
        service_level="STANDARD",
        preferred_carrier="BlueDart",
    )
    prod = DimProduct(
        product_id="SPH-A15-128",
        product_name="Aster 15 128GB",
        product_family="Mid-range",
        ram="8GB",
        storage="128GB",
        display="6.5in AMOLED",
        model_revision="REV-C",
        standard_cycle_sec=48,
        standard_unit_cost_inr=11800,
        active_from=date(2026, 7, 1),
        active_to=date(2027, 12, 31),
    )
    plant = DimPlant(
        plant_id="IN-KA-01",
        plant_name="Bengaluru Plant",
        country="India",
        state="Karnataka",
        timezone="Asia/Kolkata",
        calendar_id="CAL-01",
        currency="INR",
    )
    co1 = FactCustomerOrder(
        customer_order_id="CO-PROMISE-1",
        customer_id="CUS-001",
        product_id="SPH-A15-128",
        order_date=date(2026, 8, 1),
        requested_delivery_date=date(2026, 8, 15),
        confirmed_delivery_date=date(2026, 8, 15),
        order_qty=100,
        shipped_qty=0,
        unit_price_inr=15000,
        order_status="OPEN",
        priority="HIGH",
        channel="DIRECT",
    )
    co2 = FactCustomerOrder(
        customer_order_id="CO-PROMISE-2",
        customer_id="CUS-002",
        product_id="SPH-A15-128",
        order_date=date(2026, 8, 2),
        requested_delivery_date=date(2026, 8, 20),
        confirmed_delivery_date=date(2026, 8, 20),
        order_qty=200,
        shipped_qty=0,
        unit_price_inr=15000,
        order_status="OPEN",
        priority="MEDIUM",
        channel="RETAIL",
    )
    # Inventory snapshots
    inv1 = FactInventoryDailySnapshot(
        snapshot_date=date(2026, 11, 11),
        plant_id="IN-KA-01",
        material_id="MAT-SOC-001",
        warehouse_id="RM-WH-01",
        lot_id="LOT-01",
        on_hand_qty=500,
        allocated_qty=50,
        blocked_qty=10,
        quality_hold_qty=0,
        in_transit_qty=100,
        safety_stock_qty=50,
        inventory_status="ACTIVE",
        unit_cost_inr=4000,
    )
    inv2 = FactInventoryDailySnapshot(
        snapshot_date=date(2026, 11, 11),
        plant_id="IN-KA-01",
        material_id="MAT-MEM-002",
        warehouse_id="RM-WH-01",
        lot_id="LOT-02",
        on_hand_qty=20,
        allocated_qty=10,
        blocked_qty=0,
        quality_hold_qty=0,
        in_transit_qty=50,
        safety_stock_qty=10,
        inventory_status="ACTIVE",
        unit_cost_inr=1000,
    )
    inv_fg = FactInventoryDailySnapshot(
        snapshot_date=date(2026, 11, 11),
        plant_id="IN-KA-01",
        material_id="MAT-SOC-001",
        warehouse_id="FG-WH-01",
        lot_id="LOT-FG",
        on_hand_qty=150,
        allocated_qty=0,
        blocked_qty=0,
        quality_hold_qty=0,
        in_transit_qty=0,
        safety_stock_qty=10,
        inventory_status="ACTIVE",
        unit_cost_inr=5000,
    )
    session.add_all([cust, cust2, prod, plant, co1, co2, inv1, inv2, inv_fg])
    session.commit()

    yield session

    session.close()


def test_promise_check_atp(mock_db):
    """Test ATP calculation per material, shortfall detection, and limiting material."""
    res = PromiseService.check_atp(mock_db, "CO-PROMISE-1")
    assert res.customer_order_id == "CO-PROMISE-1"
    assert res.order_qty == 100
    assert len(res.materials) > 0
    # MAT-MEM-002 has only 10 usable (20 on_hand - 10 allocated), so shortfall exists for 100 required
    mem = next(m for m in res.materials if m.material_id == "MAT-MEM-002")
    assert mem.shortfall_qty > 0
    assert res.is_atp_feasible is False
    assert res.limiting_material_id is not None
    assert res.finished_goods_inventory["on_hand_qty"] >= 150


def test_promise_check_ctp(mock_db):
    """Test CTP capacity calculation based on standard cycle time."""
    res = PromiseService.check_ctp(mock_db, "CO-PROMISE-1")
    assert res.remaining_qty == 100
    assert res.standard_cycle_sec == 48
    assert res.daily_capacity_units > 0
    assert res.days_to_produce >= 1
    assert res.producible_by >= date(2026, 11, 11)


def test_recommend_promise_date(mock_db):
    """Test feasible promise date recommendation factoring lead times and transit buffer."""
    res = PromiseService.recommend_promise_date(mock_db, "CO-PROMISE-1")
    assert res.recommended_date > res.requested_delivery_date
    assert res.carrier == "DHL"
    assert res.transit_buffer_days == 4
    assert len(res.conflicts) > 0  # MATERIAL_SHORTAGE or OVERDUE


def test_propose_allocation_greedy(mock_db):
    """Test greedy allocation prioritizing HIGH priority + OTIF-95 service level."""
    res = PromiseService.propose_allocation(mock_db, product_id="SPH-A15-128")
    assert res.total_usable_inventory_units == 150
    assert len(res.allocations) == 2
    # CO-PROMISE-1 (HIGH, OTIF-95, req 100) must receive full 100
    a1 = res.allocations[0]
    assert a1.customer_order_id == "CO-PROMISE-1"
    assert a1.allocated_qty == 100
    assert a1.allocation_status == "FULL"
    # CO-PROMISE-2 (MEDIUM, req 200) receives remaining 50
    a2 = res.allocations[1]
    assert a2.customer_order_id == "CO-PROMISE-2"
    assert a2.allocated_qty == 50
    assert a2.unfulfilled_qty == 150
    assert a2.allocation_status == "PARTIAL"

