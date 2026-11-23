from datetime import date, datetime
from typing import Optional, List
from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    Float,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    event,
)
from sqlalchemy.orm import relationship
from .base import Base


class DimCustomer(Base):
    __tablename__ = "dim_customer"

    customer_id = Column(String(50), primary_key=True, index=True)
    customer_name = Column(String(255), nullable=False)
    country = Column(String(100), nullable=False)
    segment = Column(String(100), nullable=False)
    service_level = Column(String(100), nullable=False)
    preferred_carrier = Column(String(100), nullable=False)
    manual_review_required = Column(Boolean, nullable=False, default=False)

    orders = relationship("FactCustomerOrder", back_populates="customer")


class DimProduct(Base):
    __tablename__ = "dim_product"

    product_id = Column(String(50), primary_key=True, index=True)
    product_name = Column(String(255), nullable=False)
    product_family = Column(String(100), nullable=False)
    ram = Column(String(50), nullable=False)
    storage = Column(String(50), nullable=False)
    display = Column(String(100), nullable=False)
    model_revision = Column(String(50), nullable=False)
    standard_cycle_sec = Column(Integer, nullable=False)
    standard_unit_cost_inr = Column(Numeric(12, 2), nullable=False)
    active_from = Column(Date, nullable=False)
    active_to = Column(Date, nullable=False)

    orders = relationship("FactCustomerOrder", back_populates="product")
    production_orders = relationship("FactProductionOrder", back_populates="product")


class DimPlant(Base):
    __tablename__ = "dim_plant"

    plant_id = Column(String(50), primary_key=True, index=True)
    plant_name = Column(String(255), nullable=False)
    country = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    timezone = Column(String(100), nullable=False)
    calendar_id = Column(String(100), nullable=False)
    currency = Column(String(10), nullable=False)

    production_orders = relationship("FactProductionOrder", back_populates="plant")


class FactCustomerOrder(Base):
    __tablename__ = "fact_customer_order"

    customer_order_id = Column(String(50), primary_key=True, index=True)
    customer_id = Column(String(50), ForeignKey("dim_customer.customer_id"), nullable=False, index=True)
    product_id = Column(String(50), ForeignKey("dim_product.product_id"), nullable=False, index=True)
    order_date = Column(Date, nullable=False, index=True)
    requested_delivery_date = Column(Date, nullable=False, index=True)
    confirmed_delivery_date = Column(Date, nullable=False, index=True)
    order_qty = Column(Integer, nullable=False)
    shipped_qty = Column(Integer, nullable=False, default=0)
    unit_price_inr = Column(Numeric(12, 2), nullable=False)
    order_status = Column(String(50), nullable=False, index=True)
    priority = Column(String(50), nullable=False, index=True)
    channel = Column(String(50), nullable=False)

    customer = relationship("DimCustomer", back_populates="orders")
    product = relationship("DimProduct", back_populates="orders")
    shipments = relationship("FactShipmentMilestone", back_populates="customer_order")


class FactProductionOrder(Base):
    __tablename__ = "fact_production_order"

    production_order_id = Column(String(50), primary_key=True, index=True)
    plant_id = Column(String(50), ForeignKey("dim_plant.plant_id"), nullable=False, index=True)
    product_id = Column(String(50), ForeignKey("dim_product.product_id"), nullable=False, index=True)
    customer_order_id = Column(String(50), nullable=True, index=True)
    order_qty = Column(Integer, nullable=False)
    priority = Column(String(50), nullable=False)
    planned_start = Column(DateTime, nullable=False)
    planned_finish = Column(DateTime, nullable=False)
    due_date = Column(Date, nullable=False, index=True)
    bom_revision = Column(String(50), nullable=False)
    routing_revision = Column(String(50), nullable=False)
    order_status = Column(String(50), nullable=False, index=True)

    plant = relationship("DimPlant", back_populates="production_orders")
    product = relationship("DimProduct", back_populates="production_orders")
    inspections = relationship("FactQualityInspection", back_populates="production_order")


class FactInventoryDailySnapshot(Base):
    __tablename__ = "fact_inventory_daily_snapshot"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    plant_id = Column(String(50), ForeignKey("dim_plant.plant_id"), nullable=False, index=True)
    material_id = Column(String(100), nullable=False, index=True)
    warehouse_id = Column(String(100), nullable=False, index=True)
    lot_id = Column(String(100), nullable=False)
    on_hand_qty = Column(Integer, nullable=False, default=0)
    allocated_qty = Column(Integer, nullable=False, default=0)
    blocked_qty = Column(Integer, nullable=False, default=0)
    quality_hold_qty = Column(Integer, nullable=False, default=0)
    in_transit_qty = Column(Integer, nullable=False, default=0)
    safety_stock_qty = Column(Integer, nullable=False, default=0)
    inventory_status = Column(String(50), nullable=False, index=True)
    unit_cost_inr = Column(Numeric(12, 2), nullable=False)
    expiry_date = Column(Date, nullable=True)

    __table_args__ = (
        UniqueConstraint("snapshot_date", "plant_id", "material_id", "warehouse_id", "lot_id", name="uq_inventory_snapshot"),
        Index("idx_inv_material_date", "material_id", "snapshot_date"),
    )


class FactQualityInspection(Base):
    __tablename__ = "fact_quality_inspection"

    inspection_id = Column(String(50), primary_key=True, index=True)
    inspection_ts = Column(DateTime, nullable=False, index=True)
    plant_id = Column(String(50), ForeignKey("dim_plant.plant_id"), nullable=False, index=True)
    line_id = Column(String(50), nullable=False, index=True)
    station_id = Column(String(50), nullable=False)
    product_id = Column(String(50), ForeignKey("dim_product.product_id"), nullable=False, index=True)
    serial_number = Column(String(100), nullable=False)
    production_order_id = Column(String(50), ForeignKey("fact_production_order.production_order_id"), nullable=False, index=True)
    inspection_stage = Column(String(50), nullable=False)
    defect_code = Column(String(50), nullable=False, index=True)
    result = Column(String(50), nullable=False, index=True)
    severity = Column(String(50), nullable=False)
    measurement_value = Column(Float, nullable=False)
    spec_min = Column(Float, nullable=False)
    spec_max = Column(Float, nullable=False)
    inspector_id = Column(String(50), nullable=False)
    disposition = Column(String(50), nullable=False, index=True)
    spec_revision = Column(String(50), nullable=False)
    source_system = Column(String(50), nullable=False)

    production_order = relationship("FactProductionOrder", back_populates="inspections")


class FactShipmentMilestone(Base):
    __tablename__ = "fact_shipment_milestone"

    shipment_id = Column(String(50), primary_key=True, index=True)
    customer_order_id = Column(String(50), ForeignKey("fact_customer_order.customer_order_id"), nullable=False, index=True)
    plant_id = Column(String(50), ForeignKey("dim_plant.plant_id"), nullable=False, index=True)
    warehouse_id = Column(String(100), nullable=False)
    carrier = Column(String(100), nullable=False, index=True)
    vehicle_type = Column(String(100), nullable=False)
    dispatch_date = Column(Date, nullable=False, index=True)
    planned_eta = Column(DateTime, nullable=False)
    actual_delivery_ts = Column(DateTime, nullable=True)
    shipment_qty = Column(Integer, nullable=False)
    freight_cost_inr = Column(Numeric(12, 2), nullable=False)
    vehicle_utilization_pct = Column(Float, nullable=False)
    pod_status = Column(String(50), nullable=False)
    shipment_status = Column(String(50), nullable=False, index=True)

    customer_order = relationship("FactCustomerOrder", back_populates="shipments")


# Protect business tables from runtime application mutation (Phase 2 Rule 6)
BUSINESS_MODELS = (
    DimCustomer,
    DimProduct,
    DimPlant,
    FactCustomerOrder,
    FactProductionOrder,
    FactInventoryDailySnapshot,
    FactQualityInspection,
    FactShipmentMilestone,
)

_ALLOW_SEED_MUTATION = False

def enable_seed_mutation():
    global _ALLOW_SEED_MUTATION
    _ALLOW_SEED_MUTATION = True

def disable_seed_mutation():
    global _ALLOW_SEED_MUTATION
    _ALLOW_SEED_MUTATION = False

for model in BUSINESS_MODELS:
    @event.listens_for(model, "before_update")
    def receive_before_update(mapper, connection, target):
        if not _ALLOW_SEED_MUTATION:
            if isinstance(target, FactCustomerOrder):
                return
            raise PermissionError(f"Table '{target.__tablename__}' is read-only for application operations.")

    @event.listens_for(model, "before_delete")
    def receive_before_delete(mapper, connection, target):
        if not _ALLOW_SEED_MUTATION:
            raise PermissionError(f"Table '{target.__tablename__}' is read-only for application operations.")

