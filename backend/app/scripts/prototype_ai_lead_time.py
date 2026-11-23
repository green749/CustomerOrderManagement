import sys
sys.path.append('backend')
from app.database import SessionLocal
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
from app.agent.domo_client import DomoTextLLM, is_domo_configured
import math
import json
import re
from datetime import date, timedelta

def test_ai_lead_time():
    db = SessionLocal()
    try:
        # Context gathering
        completed_orders = db.query(FactProductionOrder).filter(FactProductionOrder.order_status == 'COMPLETED').all()
        durations = []
        for co in completed_orders:
            if co.planned_finish and co.planned_start:
                d = (co.planned_finish - co.planned_start).days
                if d > 0 and co.order_qty:
                    durations.append(co.order_qty / d)
        daily_avg_throughput = round(sum(durations) / len(durations), 1) if durations else 713.0
        
        competing_orders = db.query(FactProductionOrder).filter(FactProductionOrder.order_status.in_(['IN_PROGRESS', 'RELEASED'])).all()
        competing_count = len(competing_orders)
        competing_units = sum(co.order_qty or 0 for co in competing_orders)

        shipments = db.query(FactShipmentMilestone).filter(
            FactShipmentMilestone.dispatch_date.isnot(None),
            FactShipmentMilestone.actual_delivery_ts.isnot(None)
        ).limit(50).all()
        t_list = []
        for s in shipments:
            del_d = s.actual_delivery_ts.date() if hasattr(s.actual_delivery_ts, 'date') else s.actual_delivery_ts
            td = (del_d - s.dispatch_date).days
            if 0 < td <= 14:
                t_list.append(td)
        avg_transit = round(sum(t_list) / len(t_list), 1) if t_list else 3.0

        print(f"Factory Context -> Throughput: {daily_avg_throughput} units/day | Competing Orders: {competing_count} ({competing_units:,} units) | Transit: {avg_transit}d")

        # Test with 10 units
        intake_date = date.today()
        order_qty = 10
        req_date = intake_date + timedelta(days=1)
        
        prompt = f"""You are the Order Feasibility AI Agent for a discrete manufacturing plant.
Analyze the following operational factory floor data for a new customer order:
- Product: Aster 15 128GB (SPH-A15-128)
- Order Quantity: {order_qty} units
- Customer: Retailer North (CUS-001)
- Order Intake Date: {intake_date}
- Customer Requested Delivery Date: {req_date}
- Plant Daily Average Throughput: {daily_avg_throughput} units/day
- Active Competing Production Orders: {competing_count} orders ({competing_units:,} units in progress/released across lines)
- Material Availability: All BOM components on-hand, 0 shortage
- Quality Hold Rate: 1.1% historical hold rate
- Historical Carrier Transit (DHL): {avg_transit} days average to customer hub

Based on the daily average production, competing order queue backlog, material status, QA rate, and carrier transit:
Calculate the operational days required for each department along the critical path:
1. WMS (Material staging / kitting): ? days
2. MES (Assembly line wait & run based on daily average throughput and competing orders): ? days
3. QMS (Quality release & lot inspection): ? days
4. TMS (Freight transit): ? days
5. ERP (Commercial clearance): ? days

Return ONLY a valid JSON object:
{{
  "wms_days": <int>,
  "mes_days": <int>,
  "qms_days": <int>,
  "tms_days": <int>,
  "erp_days": <int>,
  "total_critical_path_days": <int>,
  "achievable_delivery_date": "YYYY-MM-DD",
  "explanation": "<concise breakdown of why each department takes these days based on competing queue and daily throughput>",
  "blockers": ["<blocker 1>"],
  "corrective_actions": ["<action 1>"]
}}"""
        llm = DomoTextLLM(max_tokens=600, temperature=0.1)
        raw = llm.invoke(prompt)
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            res = json.loads(m.group(0))
            print("\nAI Result for 10 units:")
            print("WMS Days:", res.get("wms_days"))
            print("MES Days:", res.get("mes_days"))
            print("QMS Days:", res.get("qms_days"))
            print("TMS Days:", res.get("tms_days"))
            print("Total Days:", res.get("total_critical_path_days"))
            print("Achievable Date:", res.get("achievable_delivery_date"))
            print("Explanation:", res.get("explanation"))
    finally:
        db.close()

if __name__ == '__main__':
    test_ai_lead_time()
