import pytest
from sqlalchemy import select, func
from app.models.business import (
    DimCustomer,
    DimProduct,
    DimPlant,
    FactCustomerOrder,
    FactProductionOrder,
    FactInventoryDailySnapshot,
    FactQualityInspection,
    FactShipmentMilestone,
)


def test_imported_row_counts(db_session):
    assert db_session.scalar(select(func.count(DimCustomer.customer_id))) == 4
    assert db_session.scalar(select(func.count(DimProduct.product_id))) == 3
    assert db_session.scalar(select(func.count(DimPlant.plant_id))) == 2
    assert db_session.scalar(select(func.count(FactCustomerOrder.customer_order_id))) == 1500
    assert db_session.scalar(select(func.count(FactProductionOrder.production_order_id))) == 450
    assert db_session.scalar(select(func.count(FactShipmentMilestone.shipment_id))) == 1000
    assert db_session.scalar(select(func.count(FactQualityInspection.inspection_id))) == 16000
    assert db_session.scalar(select(func.count(FactInventoryDailySnapshot.id))) == 6624


def test_business_tables_are_read_only(db_session):
    """Verify that runtime application operations cannot mutate business records (Phase 2 Rule 6)."""
    cust = db_session.query(DimCustomer).first()
    assert cust is not None
    cust.customer_name = "Modified Name Attempt"

    with pytest.raises(PermissionError) as exc_info:
        db_session.flush()

    assert "is read-only for application operations" in str(exc_info.value)
    db_session.rollback()

