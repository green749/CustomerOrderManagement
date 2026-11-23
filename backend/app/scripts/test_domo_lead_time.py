import sys
sys.path.append('backend')
from app.agent.domo_client import DomoTextLLM

llm = DomoTextLLM()

prompt = """You are the Order Feasibility AI Agent for a discrete manufacturing plant.
Analyze the following operational factory floor data for a new customer order:
- Product: Aster 15 128GB (SPH-A15-128)
- Order Quantity: 3000 units
- Customer: Retailer North (CUS-001)
- Order Intake Date: 2026-11-14
- Requested Delivery Date: 2026-12-05
- Plant Daily Average Throughput: 713 units/day
- Active Competing Production Orders: 206 orders (280,945 units currently in progress/released across lines)
- Material Availability: All BOM components on-hand, 0 shortage
- Historical Carrier Transit: DHL average 3.0 days to customer regional hub
- Quality Hold Rate: 1.1% historical hold rate

Based on the daily average production, competing order queue, material status, QA rate, and carrier transit:
Calculate how many days EACH department takes:
1. WMS (Material kitting): ? days
2. MES (Assembly line wait & run): ? days
3. QMS (Quality release): ? days
4. TMS (Freight transit): ? days

Return ONLY a valid JSON object with:
{
  "wms_days": <int>,
  "mes_days": <int>,
  "qms_days": <int>,
  "tms_days": <int>,
  "total_critical_path_days": <int>,
  "achievable_delivery_date": "YYYY-MM-DD",
  "explanation": "<short executive reasoning>"
}
"""

try:
    resp = llm.invoke(prompt)
    print("Domo AI Response:")
    print(resp)
except Exception as e:
    print("Error:", e)
