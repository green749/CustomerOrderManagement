import os
import sys
import uuid
import logging
from datetime import datetime, date, timezone
from pathlib import Path
from decimal import Decimal
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import select, func, text

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.database import engine, SessionLocal
from app.models.business import (
    DimCustomer,
    DimProduct,
    DimPlant,
    FactCustomerOrder,
    FactProductionOrder,
    FactInventoryDailySnapshot,
    FactQualityInspection,
    FactShipmentMilestone,
    enable_seed_mutation,
    disable_seed_mutation,
)
from app.models.operational import (
    FactBOMComponent,
    FactEngineeringChange,
    DimMaterial,
    DimSupplier,
    FactPurchaseOrderReceipt,
    FactRFQQuote,
    DimProductionLine,
    DimStation,
    DimProductRouting,
    DimMachine,
    DimShiftCalendar,
    FactDowntimeEvent,
    FactMaintenanceWorkOrder,
    MartDailyLineShiftKPI,
    DimDefectCode,
    FactNCRCAPA,
    FactManufacturingCost,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("importer")


def parse_date(val):
    if pd.isna(val) or val is None or str(val).strip() == "" or str(val).lower() == "nan":
        return None
    s = str(val).strip()
    if "T" in s:
        s = s.split("T")[0]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def parse_datetime(val):
    if pd.isna(val) or val is None or str(val).strip() == "" or str(val).lower() == "nan":
        return None
    s = str(val).strip().replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def parse_bool(val, default=False):
    if pd.isna(val) or val is None:
        return default
    s = str(val).strip().lower()
    return s in ("true", "1", "t", "yes", "y")


def parse_int(val, default=0):
    if pd.isna(val) or val is None or str(val).strip() == "":
        return default
    try:
        return int(float(str(val).strip()))
    except Exception:
        return default


def parse_float(val, default=0.0):
    if pd.isna(val) or val is None or str(val).strip() == "":
        return default
    try:
        return float(str(val).strip())
    except Exception:
        return default


def parse_decimal(val, default="0.00"):
    if pd.isna(val) or val is None or str(val).strip() == "":
        return Decimal(default)
    try:
        return Decimal(str(val).strip())
    except Exception:
        return Decimal(default)


def run_operational_import(data_dir: str = None) -> dict:
    if data_dir is None:
        # Check both potential data directories
        p1 = Path(__file__).resolve().parent.parent.parent.parent / "data" / "data"
        p2 = Path(__file__).resolve().parent.parent.parent.parent / "data"
        data_dir = str(p1) if p1.exists() else str(p2)

    data_path = Path(data_dir)
    batch_id = f"BATCH-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    start_time = datetime.utcnow()

    logger.info(f"Starting Idempotent Operational Import. Batch ID: {batch_id}")
    logger.info(f"Source Data Path: {data_path.resolve()}")

    report = {
        "batch_id": batch_id,
        "started_at": start_time.isoformat(),
        "source_directory": str(data_path.resolve()),
        "tables": {},
        "unmapped_files": [],
        "errors": [],
    }

    db: Session = SessionLocal()
    enable_seed_mutation()

    try:
        # ====================================================================
        # 1. MMS: dim_material.csv
        # ====================================================================
        fn = "dim_material.csv"
        fp = data_path / fn
        if fp.exists():
            df = pd.read_csv(fp)
            t_name = "dim_material"
            stats = {"source_file": fn, "file_records": len(df), "inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
            existing = {m.material_id: m for m in db.query(DimMaterial).all()}

            for _, row in df.iterrows():
                try:
                    mid = str(row["material_id"]).strip()
                    if mid in existing:
                        stats["skipped"] += 1
                    else:
                        m = DimMaterial(
                            material_id=mid,
                            material_name=str(row["material_name"]).strip(),
                            material_category=str(row["material_category"]).strip(),
                            uom=str(row["uom"]).strip() if pd.notna(row.get("uom")) else "EA",
                            standard_price_inr=parse_decimal(row.get("standard_price_inr")),
                            lead_time_days=parse_int(row.get("lead_time_days"), 7),
                            safety_stock_qty=parse_int(row.get("safety_stock_qty"), 0),
                            moq=parse_int(row.get("moq"), 1),
                            shelf_life_days=parse_int(row.get("shelf_life_days"), 0),
                            approved_vendor_required=parse_bool(row.get("approved_vendor_required"), True),
                            source_file=fn,
                            source_row_id=mid,
                            imported_at=datetime.utcnow(),
                            import_batch_id=batch_id,
                        )
                        db.add(m)
                        existing[mid] = m
                        stats["inserted"] += 1
                except Exception as ex:
                    stats["failed"] += 1
                    stats.setdefault("error_details", []).append(f"Row {mid}: {str(ex)}")
            db.commit()
            report["tables"][t_name] = stats
            logger.info(f"Imported {t_name}: {stats['inserted']} inserted, {stats['skipped']} skipped.")

        # ====================================================================
        # 2. MMS: dim_supplier.csv
        # ====================================================================
        fn = "dim_supplier.csv"
        fp = data_path / fn
        if fp.exists():
            df = pd.read_csv(fp)
            t_name = "dim_supplier"
            stats = {"source_file": fn, "file_records": len(df), "inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
            existing = {s.supplier_id: s for s in db.query(DimSupplier).all()}

            for _, row in df.iterrows():
                try:
                    sid = str(row["supplier_id"]).strip()
                    if sid in existing:
                        stats["skipped"] += 1
                    else:
                        s = DimSupplier(
                            supplier_id=sid,
                            supplier_name=str(row["supplier_name"]).strip(),
                            country=str(row["country"]).strip(),
                            material_category=str(row["material_category"]).strip(),
                            approved_status=str(row["approved_status"]).strip(),
                            quality_certification=str(row.get("quality_certification", "")).strip(),
                            standard_lead_time_days=parse_int(row.get("standard_lead_time_days"), 14),
                            payment_terms=str(row.get("payment_terms", "NET 30")).strip(),
                            risk_tier=str(row.get("risk_tier", "MEDIUM")).strip(),
                            source_file=fn,
                            source_row_id=sid,
                            imported_at=datetime.utcnow(),
                            import_batch_id=batch_id,
                        )
                        db.add(s)
                        existing[sid] = s
                        stats["inserted"] += 1
                except Exception as ex:
                    stats["failed"] += 1
            db.commit()
            report["tables"][t_name] = stats
            logger.info(f"Imported {t_name}: {stats['inserted']} inserted, {stats['skipped']} skipped.")

        # ====================================================================
        # 3. PLM: fact_bom_component.csv
        # ====================================================================
        fn = "fact_bom_component.csv"
        fp = data_path / fn
        if fp.exists():
            df = pd.read_csv(fp)
            t_name = "fact_bom_component"
            stats = {"source_file": fn, "file_records": len(df), "inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
            existing = {(b.bom_id, b.product_id, b.material_id): b for b in db.query(FactBOMComponent).all()}

            for _, row in df.iterrows():
                try:
                    key = (str(row["bom_id"]).strip(), str(row["product_id"]).strip(), str(row["material_id"]).strip())
                    if key in existing:
                        stats["skipped"] += 1
                    else:
                        b = FactBOMComponent(
                            bom_id=key[0],
                            product_id=key[1],
                            material_id=key[2],
                            component_qty=parse_int(row.get("component_qty"), 1),
                            scrap_factor=parse_float(row.get("scrap_factor"), 0.0),
                            revision=str(row.get("revision", "REV-A")).strip(),
                            effective_from=parse_date(row.get("effective_from")),
                            effective_to=parse_date(row.get("effective_to")),
                            source_file=fn,
                            source_row_id=f"{key[0]}_{key[1]}_{key[2]}",
                            imported_at=datetime.utcnow(),
                            import_batch_id=batch_id,
                        )
                        db.add(b)
                        existing[key] = b
                        stats["inserted"] += 1
                except Exception as ex:
                    stats["failed"] += 1
            db.commit()
            report["tables"][t_name] = stats
            logger.info(f"Imported {t_name}: {stats['inserted']} inserted, {stats['skipped']} skipped.")

        # ====================================================================
        # 4. MES: dim_production_line.csv
        # ====================================================================
        fn = "dim_production_line.csv"
        fp = data_path / fn
        if fp.exists():
            df = pd.read_csv(fp)
            t_name = "dim_production_line"
            stats = {"source_file": fn, "file_records": len(df), "inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
            existing = {l.line_id: l for l in db.query(DimProductionLine).all()}

            for _, row in df.iterrows():
                try:
                    lid = str(row["line_id"]).strip()
                    if lid in existing:
                        stats["skipped"] += 1
                    else:
                        line = DimProductionLine(
                            line_id=lid,
                            plant_id=str(row["plant_id"]).strip(),
                            line_type=str(row["line_type"]).strip(),
                            nominal_capacity_per_hour=parse_int(row.get("nominal_capacity_per_hour"), 100),
                            takt_time_sec=parse_float(row.get("takt_time_sec"), 10.0),
                            area=str(row.get("area", "")).strip(),
                            source_file=fn,
                            source_row_id=lid,
                            imported_at=datetime.utcnow(),
                            import_batch_id=batch_id,
                        )
                        db.add(line)
                        existing[lid] = line
                        stats["inserted"] += 1
                except Exception as ex:
                    stats["failed"] += 1
            db.commit()
            report["tables"][t_name] = stats
            logger.info(f"Imported {t_name}: {stats['inserted']} inserted, {stats['skipped']} skipped.")

        # ====================================================================
        # 5. MES: dim_station.csv
        # ====================================================================
        fn = "dim_station.csv"
        fp = data_path / fn
        if fp.exists():
            df = pd.read_csv(fp)
            t_name = "dim_station"
            stats = {"source_file": fn, "file_records": len(df), "inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
            existing = {s.station_id: s for s in db.query(DimStation).all()}

            for _, row in df.iterrows():
                try:
                    sid = str(row["station_id"]).strip()
                    if sid in existing:
                        stats["skipped"] += 1
                    else:
                        st = DimStation(
                            station_id=sid,
                            station_name=str(row["station_name"]).strip(),
                            process_area=str(row["process_area"]).strip(),
                            sequence_no=parse_int(row.get("sequence_no"), 1),
                            critical_control_point=parse_bool(row.get("critical_control_point"), False),
                            source_file=fn,
                            source_row_id=sid,
                            imported_at=datetime.utcnow(),
                            import_batch_id=batch_id,
                        )
                        db.add(st)
                        existing[sid] = st
                        stats["inserted"] += 1
                except Exception as ex:
                    stats["failed"] += 1
            db.commit()
            report["tables"][t_name] = stats
            logger.info(f"Imported {t_name}: {stats['inserted']} inserted, {stats['skipped']} skipped.")

        # ====================================================================
        # 6. MES: dim_product_routing.csv
        # ====================================================================
        fn = "dim_product_routing.csv"
        fp = data_path / fn
        if fp.exists():
            df = pd.read_csv(fp)
            t_name = "dim_product_routing"
            stats = {"source_file": fn, "file_records": len(df), "inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
            existing = {(r.routing_id, r.operation_seq): r for r in db.query(DimProductRouting).all()}

            for _, row in df.iterrows():
                try:
                    key = (str(row["routing_id"]).strip(), parse_int(row["operation_seq"]))
                    if key in existing:
                        stats["skipped"] += 1
                    else:
                        rt = DimProductRouting(
                            routing_id=key[0],
                            product_id=str(row["product_id"]).strip(),
                            operation_seq=key[1],
                            station_id=str(row["station_id"]).strip(),
                            standard_cycle_sec=parse_int(row.get("standard_cycle_sec"), 10),
                            setup_min=parse_int(row.get("setup_min"), 0),
                            quality_gate=parse_bool(row.get("quality_gate"), False),
                            revision=str(row.get("revision", "")).strip(),
                            source_file=fn,
                            source_row_id=f"{key[0]}_{key[1]}",
                            imported_at=datetime.utcnow(),
                            import_batch_id=batch_id,
                        )
                        db.add(rt)
                        existing[key] = rt
                        stats["inserted"] += 1
                except Exception as ex:
                    stats["failed"] += 1
            db.commit()
            report["tables"][t_name] = stats
            logger.info(f"Imported {t_name}: {stats['inserted']} inserted, {stats['skipped']} skipped.")

        # ====================================================================
        # 7. MES: dim_machine.csv
        # ====================================================================
        fn = "dim_machine.csv"
        fp = data_path / fn
        if fp.exists():
            df = pd.read_csv(fp)
            t_name = "dim_machine"
            stats = {"source_file": fn, "file_records": len(df), "inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
            existing = {m.machine_id: m for m in db.query(DimMachine).all()}

            for _, row in df.iterrows():
                try:
                    mid = str(row["machine_id"]).strip()
                    if mid in existing:
                        stats["skipped"] += 1
                    else:
                        mach = DimMachine(
                            machine_id=mid,
                            machine_name=str(row["machine_name"]).strip(),
                            machine_type=str(row["machine_type"]).strip(),
                            line_id=str(row["line_id"]).strip(),
                            plant_id=str(row["plant_id"]).strip(),
                            criticality=str(row.get("criticality", "B")).strip(),
                            commissioned_date=parse_date(row.get("commissioned_date")),
                            planned_maintenance_interval_days=parse_int(row.get("planned_maintenance_interval_days"), 30),
                            source_file=fn,
                            source_row_id=mid,
                            imported_at=datetime.utcnow(),
                            import_batch_id=batch_id,
                        )
                        db.add(mach)
                        existing[mid] = mach
                        stats["inserted"] += 1
                except Exception as ex:
                    stats["failed"] += 1
            db.commit()
            report["tables"][t_name] = stats
            logger.info(f"Imported {t_name}: {stats['inserted']} inserted, {stats['skipped']} skipped.")

        # ====================================================================
        # 8. MES: dim_shift_calendar.csv
        # ====================================================================
        fn = "dim_shift_calendar.csv"
        fp = data_path / fn
        if fp.exists():
            df = pd.read_csv(fp)
            t_name = "dim_shift_calendar"
            stats = {"source_file": fn, "file_records": len(df), "inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
            existing = {(sc.calendar_date, sc.shift_id): sc for sc in db.query(DimShiftCalendar).all()}

            for _, row in df.iterrows():
                try:
                    cdate = parse_date(row["calendar_date"])
                    sid = str(row["shift_id"]).strip()
                    key = (cdate, sid)
                    if key in existing:
                        stats["skipped"] += 1
                    else:
                        sc = DimShiftCalendar(
                            calendar_date=cdate,
                            shift_id=sid,
                            shift_start=parse_datetime(row.get("shift_start")),
                            shift_end=parse_datetime(row.get("shift_end")),
                            planned_minutes=parse_int(row.get("planned_minutes"), 420),
                            break_minutes=parse_int(row.get("break_minutes"), 30),
                            is_working_day=parse_bool(row.get("is_working_day"), True),
                            source_file=fn,
                            source_row_id=f"{cdate}_{sid}",
                            imported_at=datetime.utcnow(),
                            import_batch_id=batch_id,
                        )
                        db.add(sc)
                        existing[key] = sc
                        stats["inserted"] += 1
                except Exception as ex:
                    stats["failed"] += 1
            db.commit()
            report["tables"][t_name] = stats
            logger.info(f"Imported {t_name}: {stats['inserted']} inserted, {stats['skipped']} skipped.")

        # ====================================================================
        # 9. QMS: dim_defect_code.csv
        # ====================================================================
        fn = "dim_defect_code.csv"
        fp = data_path / fn
        if fp.exists():
            df = pd.read_csv(fp)
            t_name = "dim_defect_code"
            stats = {"source_file": fn, "file_records": len(df), "inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
            existing = {d.defect_code: d for d in db.query(DimDefectCode).all()}

            for _, row in df.iterrows():
                try:
                    dc = str(row["defect_code"]).strip()
                    if dc in existing:
                        stats["skipped"] += 1
                    else:
                        d = DimDefectCode(
                            defect_code=dc,
                            defect_name=str(row["defect_name"]).strip(),
                            defect_category=str(row["defect_category"]).strip(),
                            severity=str(row.get("severity", "MINOR")).strip(),
                            disposition_default=str(row.get("disposition_default", "REWORK")).strip(),
                            source_file=fn,
                            source_row_id=dc,
                            imported_at=datetime.utcnow(),
                            import_batch_id=batch_id,
                        )
                        db.add(d)
                        existing[dc] = d
                        stats["inserted"] += 1
                except Exception as ex:
                    stats["failed"] += 1
            db.commit()
            report["tables"][t_name] = stats
            logger.info(f"Imported {t_name}: {stats['inserted']} inserted, {stats['skipped']} skipped.")

        # ====================================================================
        # 10. QMS: fact_ncr_capa.csv
        # ====================================================================
        fn = "fact_ncr_capa.csv"
        fp = data_path / fn
        if fp.exists():
            df = pd.read_csv(fp)
            t_name = "fact_ncr_capa"
            stats = {"source_file": fn, "file_records": len(df), "inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
            existing = {n.ncr_id: n for n in db.query(FactNCRCAPA).all()}

            for _, row in df.iterrows():
                try:
                    nid = str(row["ncr_id"]).strip()
                    if nid in existing:
                        stats["skipped"] += 1
                    else:
                        n = FactNCRCAPA(
                            ncr_id=nid,
                            inspection_id=str(row["inspection_id"]).strip(),
                            opened_ts=parse_datetime(row.get("opened_ts")),
                            defect_code=str(row.get("defect_code", "")).strip(),
                            root_cause_category=str(row.get("root_cause_category", "")).strip(),
                            containment_action=str(row.get("containment_action", "")).strip(),
                            owner_id=str(row.get("owner_id", "")).strip(),
                            capa_due_date=parse_date(row.get("capa_due_date")),
                            capa_status=str(row.get("capa_status", "OPEN")).strip(),
                            effectiveness_check=str(row.get("effectiveness_check", "PENDING")).strip(),
                            source_file=fn,
                            source_row_id=nid,
                            imported_at=datetime.utcnow(),
                            import_batch_id=batch_id,
                        )
                        db.add(n)
                        existing[nid] = n
                        stats["inserted"] += 1
                except Exception as ex:
                    stats["failed"] += 1
            db.commit()
            report["tables"][t_name] = stats
            logger.info(f"Imported {t_name}: {stats['inserted']} inserted, {stats['skipped']} skipped.")

        # ====================================================================
        # 11. MMS: fact_purchase_order_receipt.csv
        # ====================================================================
        fn = "fact_purchase_order_receipt.csv"
        fp = data_path / fn
        if fp.exists():
            df = pd.read_csv(fp)
            t_name = "fact_purchase_order_receipt"
            stats = {"source_file": fn, "file_records": len(df), "inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
            existing = {(p.po_id, p.po_line): p for p in db.query(FactPurchaseOrderReceipt).all()}

            for _, row in df.iterrows():
                try:
                    key = (str(row["po_id"]).strip(), parse_int(row.get("po_line"), 1))
                    if key in existing:
                        stats["skipped"] += 1
                    else:
                        po = FactPurchaseOrderReceipt(
                            po_id=key[0],
                            po_line=key[1],
                            supplier_id=str(row["supplier_id"]).strip(),
                            material_id=str(row["material_id"]).strip(),
                            plant_id=str(row["plant_id"]).strip(),
                            po_date=parse_date(row.get("po_date")),
                            promised_date=parse_date(row.get("promised_date")),
                            receipt_date=parse_date(row.get("receipt_date")),
                            ordered_qty=parse_int(row.get("ordered_qty"), 0),
                            received_qty=parse_int(row.get("received_qty"), 0),
                            unit_price_inr=parse_decimal(row.get("unit_price_inr")),
                            currency=str(row.get("currency", "INR")).strip(),
                            po_status=str(row.get("po_status", "OPEN")).strip(),
                            incoterm=str(row.get("incoterm", "FOB")).strip(),
                            source_file=fn,
                            source_row_id=f"{key[0]}_{key[1]}",
                            imported_at=datetime.utcnow(),
                            import_batch_id=batch_id,
                        )
                        db.add(po)
                        existing[key] = po
                        stats["inserted"] += 1
                except Exception as ex:
                    stats["failed"] += 1
            db.commit()
            report["tables"][t_name] = stats
            logger.info(f"Imported {t_name}: {stats['inserted']} inserted, {stats['skipped']} skipped.")

        # ====================================================================
        # 12. MMS: fact_rfq_quote.csv
        # ====================================================================
        fn = "fact_rfq_quote.csv"
        fp = data_path / fn
        if fp.exists():
            df = pd.read_csv(fp)
            t_name = "fact_rfq_quote"
            stats = {"source_file": fn, "file_records": len(df), "inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
            existing = {r.rfq_id: r for r in db.query(FactRFQQuote).all()}

            for _, row in df.iterrows():
                try:
                    rid = str(row["rfq_id"]).strip()
                    if rid in existing:
                        stats["skipped"] += 1
                    else:
                        rfq = FactRFQQuote(
                            rfq_id=rid,
                            material_id=str(row["material_id"]).strip(),
                            supplier_id=str(row["supplier_id"]).strip(),
                            request_date=parse_date(row.get("request_date")),
                            quoted_unit_price_inr=parse_decimal(row.get("quoted_unit_price_inr")),
                            moq=parse_int(row.get("moq"), 1),
                            lead_time_days=parse_int(row.get("lead_time_days"), 14),
                            quote_valid_days=parse_int(row.get("quote_valid_days"), 30),
                            technical_compliance=str(row.get("technical_compliance", "COMPLIANT")).strip(),
                            commercial_score=parse_float(row.get("commercial_score"), 0.0),
                            recommendation_rank=parse_int(row.get("recommendation_rank"), 1),
                            approval_status=str(row.get("approval_status", "PENDING")).strip(),
                            source_file=fn,
                            source_row_id=rid,
                            imported_at=datetime.utcnow(),
                            import_batch_id=batch_id,
                        )
                        db.add(rfq)
                        existing[rid] = rfq
                        stats["inserted"] += 1
                except Exception as ex:
                    stats["failed"] += 1
            db.commit()
            report["tables"][t_name] = stats
            logger.info(f"Imported {t_name}: {stats['inserted']} inserted, {stats['skipped']} skipped.")

        # ====================================================================
        # 13. MES: fact_downtime_event.csv
        # ====================================================================
        fn = "fact_downtime_event.csv"
        fp = data_path / fn
        if fp.exists():
            df = pd.read_csv(fp)
            t_name = "fact_downtime_event"
            stats = {"source_file": fn, "file_records": len(df), "inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
            existing = {d.downtime_id: d for d in db.query(FactDowntimeEvent).all()}

            for _, row in df.iterrows():
                try:
                    did = str(row["downtime_id"]).strip()
                    if did in existing:
                        stats["skipped"] += 1
                    else:
                        dt = FactDowntimeEvent(
                            downtime_id=did,
                            machine_id=str(row["machine_id"]).strip(),
                            plant_id=str(row["plant_id"]).strip(),
                            line_id=str(row["line_id"]).strip(),
                            start_ts=parse_datetime(row.get("start_ts")),
                            duration_min=parse_int(row.get("duration_min"), 0),
                            reason_code=str(row.get("reason_code", "UNKNOWN")).strip(),
                            impact_units=parse_int(row.get("impact_units"), 0),
                            maintenance_required=parse_bool(row.get("maintenance_required"), False),
                            acknowledged_by=str(row.get("acknowledged_by", "")).strip() if pd.notna(row.get("acknowledged_by")) else None,
                            closure_status=str(row.get("closure_status", "CLOSED")).strip(),
                            source_file=fn,
                            source_row_id=did,
                            imported_at=datetime.utcnow(),
                            import_batch_id=batch_id,
                        )
                        db.add(dt)
                        existing[did] = dt
                        stats["inserted"] += 1
                except Exception as ex:
                    stats["failed"] += 1
            db.commit()
            report["tables"][t_name] = stats
            logger.info(f"Imported {t_name}: {stats['inserted']} inserted, {stats['skipped']} skipped.")

        # ====================================================================
        # 14. MES: fact_maintenance_work_order.csv
        # ====================================================================
        fn = "fact_maintenance_work_order.csv"
        fp = data_path / fn
        if fp.exists():
            df = pd.read_csv(fp)
            t_name = "fact_maintenance_work_order"
            stats = {"source_file": fn, "file_records": len(df), "inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
            existing = {w.work_order_id: w for w in db.query(FactMaintenanceWorkOrder).all()}

            for _, row in df.iterrows():
                try:
                    wid = str(row["work_order_id"]).strip()
                    if wid in existing:
                        stats["skipped"] += 1
                    else:
                        mwo = FactMaintenanceWorkOrder(
                            work_order_id=wid,
                            machine_id=str(row["machine_id"]).strip(),
                            plant_id=str(row["plant_id"]).strip(),
                            created_ts=parse_datetime(row.get("created_ts")),
                            maintenance_type=str(row.get("maintenance_type", "PREVENTATIVE")).strip(),
                            failure_mode=str(row.get("failure_mode", "")).strip(),
                            priority=str(row.get("priority", "P3")).strip(),
                            planned_start=parse_datetime(row.get("planned_start")),
                            actual_start=parse_datetime(row.get("actual_start")),
                            downtime_avoided_estimate_min=parse_int(row.get("downtime_avoided_estimate_min"), 0),
                            status=str(row.get("status", "COMPLETED")).strip(),
                            technician_id=str(row.get("technician_id", "")).strip() if pd.notna(row.get("technician_id")) else None,
                            source_file=fn,
                            source_row_id=wid,
                            imported_at=datetime.utcnow(),
                            import_batch_id=batch_id,
                        )
                        db.add(mwo)
                        existing[wid] = mwo
                        stats["inserted"] += 1
                except Exception as ex:
                    stats["failed"] += 1
            db.commit()
            report["tables"][t_name] = stats
            logger.info(f"Imported {t_name}: {stats['inserted']} inserted, {stats['skipped']} skipped.")

        # ====================================================================
        # 15. PLM: fact_engineering_change.csv
        # ====================================================================
        fn = "fact_engineering_change.csv"
        fp = data_path / fn
        if fp.exists():
            df = pd.read_csv(fp)
            t_name = "fact_engineering_change"
            stats = {"source_file": fn, "file_records": len(df), "inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
            existing = {e.change_request_id: e for e in db.query(FactEngineeringChange).all()}

            for _, row in df.iterrows():
                try:
                    cid = str(row["change_request_id"]).strip()
                    if cid in existing:
                        stats["skipped"] += 1
                    else:
                        ec = FactEngineeringChange(
                            change_request_id=cid,
                            change_type=str(row.get("change_type", "BOM_REVISION")).strip(),
                            product_id=str(row["product_id"]).strip(),
                            part_id=str(row["part_id"]).strip(),
                            old_revision=str(row["old_revision"]).strip(),
                            new_revision=str(row["new_revision"]).strip(),
                            request_date=parse_date(row.get("request_date")),
                            cut_in_date=parse_date(row.get("cut_in_date")),
                            affected_wip_qty=parse_int(row.get("affected_wip_qty"), 0),
                            affected_inventory_qty=parse_int(row.get("affected_inventory_qty"), 0),
                            engineering_approval=str(row.get("engineering_approval", "APPROVED")).strip(),
                            quality_approval=str(row.get("quality_approval", "APPROVED")).strip(),
                            implementation_status=str(row.get("implementation_status", "PLANNED")).strip(),
                            source_file=fn,
                            source_row_id=cid,
                            imported_at=datetime.utcnow(),
                            import_batch_id=batch_id,
                        )
                        db.add(ec)
                        existing[cid] = ec
                        stats["inserted"] += 1
                except Exception as ex:
                    stats["failed"] += 1
            db.commit()
            report["tables"][t_name] = stats
            logger.info(f"Imported {t_name}: {stats['inserted']} inserted, {stats['skipped']} skipped.")

        # ====================================================================
        # 16. ERP: fact_manufacturing_cost.csv
        # ====================================================================
        fn = "fact_manufacturing_cost.csv"
        fp = data_path / fn
        if fp.exists():
            df = pd.read_csv(fp)
            t_name = "fact_manufacturing_cost"
            stats = {"source_file": fn, "file_records": len(df), "inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
            existing = {c.cost_record_id: c for c in db.query(FactManufacturingCost).all()}

            for _, row in df.iterrows():
                try:
                    cid = str(row["cost_record_id"]).strip()
                    if cid in existing:
                        stats["skipped"] += 1
                    else:
                        mc = FactManufacturingCost(
                            cost_record_id=cid,
                            posting_ts=parse_datetime(row.get("posting_ts")),
                            plant_id=str(row["plant_id"]).strip(),
                            line_id=str(row["line_id"]).strip(),
                            production_order_id=str(row["production_order_id"]).strip(),
                            product_id=str(row["product_id"]).strip(),
                            produced_qty=parse_int(row.get("produced_qty"), 0),
                            material_cost_inr=parse_decimal(row.get("material_cost_inr")),
                            labour_cost_inr=parse_decimal(row.get("labour_cost_inr")),
                            machine_cost_inr=parse_decimal(row.get("machine_cost_inr")),
                            energy_cost_inr=parse_decimal(row.get("energy_cost_inr")),
                            scrap_rework_cost_inr=parse_decimal(row.get("scrap_rework_cost_inr")),
                            standard_cost_per_unit_inr=parse_decimal(row.get("standard_cost_per_unit_inr")),
                            currency=str(row.get("currency", "INR")).strip(),
                            costing_version=str(row.get("costing_version", "")).strip(),
                            source_file=fn,
                            source_row_id=cid,
                            imported_at=datetime.utcnow(),
                            import_batch_id=batch_id,
                        )
                        db.add(mc)
                        existing[cid] = mc
                        stats["inserted"] += 1
                except Exception as ex:
                    stats["failed"] += 1
            db.commit()
            report["tables"][t_name] = stats
            logger.info(f"Imported {t_name}: {stats['inserted']} inserted, {stats['skipped']} skipped.")

        # ====================================================================
        # 17. MES: mart_daily_line_shift_kpi.csv
        # ====================================================================
        fn = "mart_daily_line_shift_kpi.csv"
        fp = data_path / fn
        if fp.exists():
            df = pd.read_csv(fp)
            t_name = "mart_daily_line_shift_kpi"
            stats = {"source_file": fn, "file_records": len(df), "inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
            existing_count = db.query(func.count(MartDailyLineShiftKPI.id)).scalar() or 0
            if existing_count >= len(df):
                stats["skipped"] = existing_count
            else:
                for _, row in df.iterrows():
                    try:
                        kpi = MartDailyLineShiftKPI(
                            event_date=parse_date(row.get("event_date")),
                            plant_id=str(row["plant_id"]).strip(),
                            line_id=str(row["line_id"]).strip(),
                            shift_id=str(row["shift_id"]).strip(),
                            product_id=str(row["product_id"]).strip(),
                            target_qty=parse_int(row.get("target_qty"), 0),
                            actual_qty=parse_int(row.get("actual_qty"), 0),
                            good_qty=parse_int(row.get("good_qty"), 0),
                            reject_qty=parse_int(row.get("reject_qty"), 0),
                            rework_qty=parse_int(row.get("rework_qty"), 0),
                            downtime_min=parse_int(row.get("downtime_min"), 0),
                            plan_attainment_pct=parse_float(row.get("plan_attainment_pct"), 0.0),
                            fpy_pct=parse_float(row.get("fpy_pct"), 0.0),
                            availability_pct=parse_float(row.get("availability_pct"), 0.0),
                            performance_pct=parse_float(row.get("performance_pct"), 0.0),
                            quality_pct=parse_float(row.get("quality_pct"), 0.0),
                            oee_pct=parse_float(row.get("oee_pct"), 0.0),
                            source_file=fn,
                            source_row_id=f"{row['event_date']}_{row['line_id']}_{row['shift_id']}",
                            imported_at=datetime.utcnow(),
                            import_batch_id=batch_id,
                        )
                        db.add(kpi)
                        stats["inserted"] += 1
                    except Exception as ex:
                        stats["failed"] += 1
                db.commit()
            report["tables"][t_name] = stats
            logger.info(f"Imported {t_name}: {stats['inserted']} inserted, {stats['skipped']} skipped.")

        # Record counts for core existing tables as well
        core_tables = [
            ("dim_customer", DimCustomer, "customer_id"),
            ("dim_product", DimProduct, "product_id"),
            ("dim_plant", DimPlant, "plant_id"),
            ("fact_customer_order", FactCustomerOrder, "customer_order_id"),
            ("fact_production_order", FactProductionOrder, "production_order_id"),
            ("fact_inventory_daily_snapshot", FactInventoryDailySnapshot, "id"),
            ("fact_quality_inspection", FactQualityInspection, "inspection_id"),
            ("fact_shipment_milestone", FactShipmentMilestone, "shipment_id"),
        ]
        for tbl_name, model_cls, pk_name in core_tables:
            csv_fn = f"{tbl_name}.csv"
            csv_fp = data_path / csv_fn
            file_recs = len(pd.read_csv(csv_fp)) if csv_fp.exists() else 0
            db_recs = db.query(func.count(getattr(model_cls, pk_name))).scalar() or 0
            report["tables"][tbl_name] = {
                "source_file": csv_fn,
                "file_records": file_recs,
                "db_records": db_recs,
                "status": "VERIFIED_EXISTING",
            }

    except Exception as exc:
        db.rollback()
        report["errors"].append(str(exc))
        logger.error(f"Import encountered critical error: {exc}", exc_info=True)
    finally:
        disable_seed_mutation()
        db.close()

    report["completed_at"] = datetime.utcnow().isoformat()
    report["duration_seconds"] = (datetime.utcnow() - start_time).total_seconds()
    logger.info(f"Import completed in {report['duration_seconds']:.2f}s.")
    return report


if __name__ == "__main__":
    rep = run_operational_import()
    import json
    print(json.dumps(rep, indent=2))
