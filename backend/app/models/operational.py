from datetime import date, datetime
from typing import Optional
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
)
from sqlalchemy.orm import relationship
from .base import Base


# ============================================================================
# PLM (Product Lifecycle Management) Entities
# ============================================================================

class FactBOMComponent(Base):
    """Product Bill of Materials component breakdown from PLM."""
    __tablename__ = "fact_bom_component"

    bom_id = Column(String(100), primary_key=True)
    product_id = Column(String(50), ForeignKey("dim_product.product_id"), primary_key=True, index=True)
    material_id = Column(String(50), primary_key=True, index=True)
    component_qty = Column(Integer, nullable=False, default=1)
    scrap_factor = Column(Float, nullable=False, default=0.0)
    revision = Column(String(50), nullable=False)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=False)

    # Provenance
    source_file = Column(String(100), nullable=True)
    source_row_id = Column(String(100), nullable=True)
    imported_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    import_batch_id = Column(String(100), nullable=True)


class FactEngineeringChange(Base):
    """Engineering Change Requests / Orders (ECO/ECR) from PLM."""
    __tablename__ = "fact_engineering_change"

    change_request_id = Column(String(50), primary_key=True, index=True)
    change_type = Column(String(50), nullable=False)
    product_id = Column(String(50), ForeignKey("dim_product.product_id"), nullable=False, index=True)
    part_id = Column(String(50), nullable=False)
    old_revision = Column(String(50), nullable=False)
    new_revision = Column(String(50), nullable=False)
    request_date = Column(Date, nullable=False)
    cut_in_date = Column(Date, nullable=False)
    affected_wip_qty = Column(Integer, nullable=False, default=0)
    affected_inventory_qty = Column(Integer, nullable=False, default=0)
    engineering_approval = Column(String(50), nullable=False)
    quality_approval = Column(String(50), nullable=False)
    implementation_status = Column(String(50), nullable=False)

    source_file = Column(String(100), nullable=True)
    source_row_id = Column(String(100), nullable=True)
    imported_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    import_batch_id = Column(String(100), nullable=True)


# ============================================================================
# MMS (Material Management System) Entities
# ============================================================================

class DimMaterial(Base):
    """Raw materials and components catalog with standard lead times and safety stock."""
    __tablename__ = "dim_material"

    material_id = Column(String(50), primary_key=True, index=True)
    material_name = Column(String(255), nullable=False)
    material_category = Column(String(100), nullable=False, index=True)
    uom = Column(String(20), nullable=False, default="EA")
    standard_price_inr = Column(Numeric(12, 2), nullable=False)
    lead_time_days = Column(Integer, nullable=False, default=7)
    safety_stock_qty = Column(Integer, nullable=False, default=0)
    moq = Column(Integer, nullable=False, default=1)
    shelf_life_days = Column(Integer, nullable=False, default=0)
    approved_vendor_required = Column(Boolean, nullable=False, default=True)

    source_file = Column(String(100), nullable=True)
    source_row_id = Column(String(100), nullable=True)
    imported_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    import_batch_id = Column(String(100), nullable=True)


class DimSupplier(Base):
    """Component suppliers and vendors with lead times and risk ratings."""
    __tablename__ = "dim_supplier"

    supplier_id = Column(String(50), primary_key=True, index=True)
    supplier_name = Column(String(255), nullable=False)
    country = Column(String(100), nullable=False)
    material_category = Column(String(100), nullable=False)
    approved_status = Column(String(50), nullable=False, index=True)
    quality_certification = Column(String(100), nullable=False)
    standard_lead_time_days = Column(Integer, nullable=False, default=14)
    payment_terms = Column(String(50), nullable=False)
    risk_tier = Column(String(50), nullable=False, index=True)

    source_file = Column(String(100), nullable=True)
    source_row_id = Column(String(100), nullable=True)
    imported_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    import_batch_id = Column(String(100), nullable=True)


class FactPurchaseOrderReceipt(Base):
    """Inbound Purchase Orders and Goods Receipts for raw materials."""
    __tablename__ = "fact_purchase_order_receipt"

    po_id = Column(String(50), primary_key=True, index=True)
    po_line = Column(Integer, primary_key=True, default=1)
    supplier_id = Column(String(50), nullable=False, index=True)
    material_id = Column(String(50), nullable=False, index=True)
    plant_id = Column(String(50), nullable=False, index=True)
    po_date = Column(Date, nullable=False)
    promised_date = Column(Date, nullable=False, index=True)
    receipt_date = Column(Date, nullable=True)
    ordered_qty = Column(Integer, nullable=False)
    received_qty = Column(Integer, nullable=False, default=0)
    unit_price_inr = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="INR")
    po_status = Column(String(50), nullable=False, index=True)
    incoterm = Column(String(20), nullable=False)

    source_file = Column(String(100), nullable=True)
    source_row_id = Column(String(100), nullable=True)
    imported_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    import_batch_id = Column(String(100), nullable=True)


class FactRFQQuote(Base):
    """Requests for Quotation and supplier pricing quotes."""
    __tablename__ = "fact_rfq_quote"

    rfq_id = Column(String(50), primary_key=True, index=True)
    material_id = Column(String(50), nullable=False, index=True)
    supplier_id = Column(String(50), nullable=False, index=True)
    request_date = Column(Date, nullable=False)
    quoted_unit_price_inr = Column(Numeric(12, 2), nullable=False)
    moq = Column(Integer, nullable=False, default=1)
    lead_time_days = Column(Integer, nullable=False)
    quote_valid_days = Column(Integer, nullable=False)
    technical_compliance = Column(String(50), nullable=False)
    commercial_score = Column(Float, nullable=False)
    recommendation_rank = Column(Integer, nullable=False)
    approval_status = Column(String(50), nullable=False)

    source_file = Column(String(100), nullable=True)
    source_row_id = Column(String(100), nullable=True)
    imported_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    import_batch_id = Column(String(100), nullable=True)


# ============================================================================
# MES (Manufacturing Execution System) Entities
# ============================================================================

class DimProductionLine(Base):
    """Manufacturing lines, rated capacities, and takt times."""
    __tablename__ = "dim_production_line"

    line_id = Column(String(50), primary_key=True, index=True)
    plant_id = Column(String(50), ForeignKey("dim_plant.plant_id"), nullable=False, index=True)
    line_type = Column(String(50), nullable=False)
    nominal_capacity_per_hour = Column(Integer, nullable=False)
    takt_time_sec = Column(Float, nullable=False)
    area = Column(String(100), nullable=False)

    source_file = Column(String(100), nullable=True)
    source_row_id = Column(String(100), nullable=True)
    imported_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    import_batch_id = Column(String(100), nullable=True)


class DimStation(Base):
    """Individual assembly and testing workstations along lines."""
    __tablename__ = "dim_station"

    station_id = Column(String(50), primary_key=True, index=True)
    station_name = Column(String(255), nullable=False)
    process_area = Column(String(100), nullable=False)
    sequence_no = Column(Integer, nullable=False)
    critical_control_point = Column(Boolean, nullable=False, default=False)

    source_file = Column(String(100), nullable=True)
    source_row_id = Column(String(100), nullable=True)
    imported_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    import_batch_id = Column(String(100), nullable=True)


class DimProductRouting(Base):
    """Routing operations, cycle times, setup durations, and quality gates per product."""
    __tablename__ = "dim_product_routing"

    routing_id = Column(String(50), primary_key=True)
    product_id = Column(String(50), ForeignKey("dim_product.product_id"), nullable=False, index=True)
    operation_seq = Column(Integer, primary_key=True)
    station_id = Column(String(50), nullable=False, index=True)
    standard_cycle_sec = Column(Integer, nullable=False)
    setup_min = Column(Integer, nullable=False, default=0)
    quality_gate = Column(Boolean, nullable=False, default=False)
    revision = Column(String(50), nullable=False)

    source_file = Column(String(100), nullable=True)
    source_row_id = Column(String(100), nullable=True)
    imported_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    import_batch_id = Column(String(100), nullable=True)


class DimMachine(Base):
    """Production machinery status, lines, and maintenance intervals."""
    __tablename__ = "dim_machine"

    machine_id = Column(String(50), primary_key=True, index=True)
    machine_name = Column(String(255), nullable=False)
    machine_type = Column(String(100), nullable=False)
    line_id = Column(String(50), nullable=False, index=True)
    plant_id = Column(String(50), nullable=False, index=True)
    criticality = Column(String(10), nullable=False)
    commissioned_date = Column(Date, nullable=False)
    planned_maintenance_interval_days = Column(Integer, nullable=False)

    source_file = Column(String(100), nullable=True)
    source_row_id = Column(String(100), nullable=True)
    imported_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    import_batch_id = Column(String(100), nullable=True)


class DimShiftCalendar(Base):
    """Operating shifts, working days, and available planned minutes."""
    __tablename__ = "dim_shift_calendar"

    calendar_date = Column(Date, primary_key=True, index=True)
    shift_id = Column(String(10), primary_key=True)
    shift_start = Column(DateTime, nullable=False)
    shift_end = Column(DateTime, nullable=False)
    planned_minutes = Column(Integer, nullable=False)
    break_minutes = Column(Integer, nullable=False)
    is_working_day = Column(Boolean, nullable=False, default=True)

    source_file = Column(String(100), nullable=True)
    source_row_id = Column(String(100), nullable=True)
    imported_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    import_batch_id = Column(String(100), nullable=True)


class FactDowntimeEvent(Base):
    """Unplanned and planned machine stoppage events."""
    __tablename__ = "fact_downtime_event"

    downtime_id = Column(String(50), primary_key=True, index=True)
    machine_id = Column(String(50), nullable=False, index=True)
    plant_id = Column(String(50), nullable=False, index=True)
    line_id = Column(String(50), nullable=False, index=True)
    start_ts = Column(DateTime, nullable=False, index=True)
    duration_min = Column(Integer, nullable=False)
    reason_code = Column(String(100), nullable=False, index=True)
    impact_units = Column(Integer, nullable=False, default=0)
    maintenance_required = Column(Boolean, nullable=False, default=False)
    acknowledged_by = Column(String(50), nullable=True)
    closure_status = Column(String(50), nullable=False, index=True)

    source_file = Column(String(100), nullable=True)
    source_row_id = Column(String(100), nullable=True)
    imported_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    import_batch_id = Column(String(100), nullable=True)


class FactMaintenanceWorkOrder(Base):
    """Preventative and corrective equipment maintenance work orders."""
    __tablename__ = "fact_maintenance_work_order"

    work_order_id = Column(String(50), primary_key=True, index=True)
    machine_id = Column(String(50), nullable=False, index=True)
    plant_id = Column(String(50), nullable=False, index=True)
    created_ts = Column(DateTime, nullable=False)
    maintenance_type = Column(String(50), nullable=False, index=True)
    failure_mode = Column(String(100), nullable=False)
    priority = Column(String(20), nullable=False)
    planned_start = Column(DateTime, nullable=False)
    actual_start = Column(DateTime, nullable=True)
    downtime_avoided_estimate_min = Column(Integer, nullable=False, default=0)
    status = Column(String(50), nullable=False, index=True)
    technician_id = Column(String(50), nullable=True)

    source_file = Column(String(100), nullable=True)
    source_row_id = Column(String(100), nullable=True)
    imported_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    import_batch_id = Column(String(100), nullable=True)


class MartDailyLineShiftKPI(Base):
    """Daily aggregated production performance, OEE, scrap, and attainment."""
    __tablename__ = "mart_daily_line_shift_kpi"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_date = Column(Date, nullable=False, index=True)
    plant_id = Column(String(50), nullable=False, index=True)
    line_id = Column(String(50), nullable=False, index=True)
    shift_id = Column(String(10), nullable=False)
    product_id = Column(String(50), nullable=False, index=True)
    target_qty = Column(Integer, nullable=False)
    actual_qty = Column(Integer, nullable=False)
    good_qty = Column(Integer, nullable=False)
    reject_qty = Column(Integer, nullable=False)
    rework_qty = Column(Integer, nullable=False)
    downtime_min = Column(Integer, nullable=False)
    plan_attainment_pct = Column(Float, nullable=False)
    fpy_pct = Column(Float, nullable=False)
    availability_pct = Column(Float, nullable=False)
    performance_pct = Column(Float, nullable=False)
    quality_pct = Column(Float, nullable=False)
    oee_pct = Column(Float, nullable=False)

    source_file = Column(String(100), nullable=True)
    source_row_id = Column(String(100), nullable=True)
    imported_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    import_batch_id = Column(String(100), nullable=True)


# ============================================================================
# QMS (Quality Management System) Entities
# ============================================================================

class DimDefectCode(Base):
    """Standardized quality defect codes and default dispositions."""
    __tablename__ = "dim_defect_code"

    defect_code = Column(String(50), primary_key=True, index=True)
    defect_name = Column(String(255), nullable=False)
    defect_category = Column(String(100), nullable=False, index=True)
    severity = Column(String(50), nullable=False, index=True)
    disposition_default = Column(String(50), nullable=False)

    source_file = Column(String(100), nullable=True)
    source_row_id = Column(String(100), nullable=True)
    imported_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    import_batch_id = Column(String(100), nullable=True)


class FactNCRCAPA(Base):
    """Non-Conformance Reports (NCR) and Corrective Actions (CAPA)."""
    __tablename__ = "fact_ncr_capa"

    ncr_id = Column(String(50), primary_key=True, index=True)
    inspection_id = Column(String(50), nullable=False, index=True)
    opened_ts = Column(DateTime, nullable=False, index=True)
    defect_code = Column(String(50), nullable=False, index=True)
    root_cause_category = Column(String(100), nullable=False)
    containment_action = Column(String(100), nullable=False)
    owner_id = Column(String(50), nullable=False)
    capa_due_date = Column(Date, nullable=False)
    capa_status = Column(String(50), nullable=False, index=True)
    effectiveness_check = Column(String(50), nullable=False)

    source_file = Column(String(100), nullable=True)
    source_row_id = Column(String(100), nullable=True)
    imported_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    import_batch_id = Column(String(100), nullable=True)


# ============================================================================
# ERP Costing Entities
# ============================================================================

class FactManufacturingCost(Base):
    """Actual and standard manufacturing costs per production order and unit."""
    __tablename__ = "fact_manufacturing_cost"

    cost_record_id = Column(String(50), primary_key=True, index=True)
    posting_ts = Column(DateTime, nullable=False, index=True)
    plant_id = Column(String(50), nullable=False, index=True)
    line_id = Column(String(50), nullable=False, index=True)
    production_order_id = Column(String(50), nullable=False, index=True)
    product_id = Column(String(50), ForeignKey("dim_product.product_id"), nullable=False, index=True)
    produced_qty = Column(Integer, nullable=False)
    material_cost_inr = Column(Numeric(14, 2), nullable=False)
    labour_cost_inr = Column(Numeric(14, 2), nullable=False)
    machine_cost_inr = Column(Numeric(14, 2), nullable=False)
    energy_cost_inr = Column(Numeric(14, 2), nullable=False)
    scrap_rework_cost_inr = Column(Numeric(14, 2), nullable=False)
    standard_cost_per_unit_inr = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="INR")
    costing_version = Column(String(50), nullable=False)

    source_file = Column(String(100), nullable=True)
    source_row_id = Column(String(100), nullable=True)
    imported_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    import_batch_id = Column(String(100), nullable=True)
