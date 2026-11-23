from typing import Any, List, Optional, Tuple
import json
import logging
import re
import time
import httpx
from langchain_core.language_models.llms import LLM
from ..config import settings

logger = logging.getLogger("manufacturing.agent.domo")


class DomoAIUnavailableException(Exception):
    """Raised when Domo AI API credentials are unconfigured or external service is unreachable."""
    pass


def is_domo_configured() -> bool:
    """Check if Domo AI integration is configured with non-placeholder credentials."""
    token = getattr(settings, "domo_token", None)
    subdomain = getattr(settings, "domo_subdomain", None)
    return bool(token and token != "your_domo_developer_token_here" and subdomain and subdomain != "your_subdomain_here")


class DomoTextLLM(LLM):
    """
    LangChain LLM wrapper for Domo AI Services Text Generation API.
    Endpoint: POST https://{subdomain}.domo.com/api/ai/v1/text/generation
    Header: X-DOMO-Developer-Token: <token>
    Model: domo.domo_ai.domogpt-small-v2.1:anthropic
    """
    temperature: float = 0.1
    max_tokens: int = 1500
    system: Optional[str] = None
    last_provider: str = "none"

    @property
    def _llm_type(self) -> str:
        return "domo-text-generation"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> str:
        # Check Domo configuration
        if not is_domo_configured():
            self.last_provider = "unconfigured"
            raise DomoAIUnavailableException(
                "Domo AI text generation is unconfigured (developer token or subdomain missing). "
                "Operational database facts will be served directly."
            )

        url = f"https://{settings.domo_subdomain}.domo.com/api/ai/v1/text/generation"
        payload = {
            "input": prompt,
            "temperature": self.temperature,
            "maxTokens": self.max_tokens,
        }
        if getattr(settings, "domo_model", None):
            payload["model"] = settings.domo_model
        else:
            payload["model"] = "domo.domo_ai.domogpt-small-v2.1:anthropic"
        if self.system:
            payload["system"] = self.system

        last_exc: Optional[Exception] = None
        backoff_seconds = (1.5, 3.0)
        for attempt in range(3):
            try:
                with httpx.Client(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
                    resp = client.post(
                        url,
                        json=payload,
                        headers={
                            "X-DOMO-Developer-Token": settings.domo_token,
                            "Content-Type": "application/json",
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    out = data.get("output", "")
                    if not out and "choices" in data and len(data["choices"]) > 0:
                        out = data["choices"][0].get("output", "")
                    for s in stop or []:
                        out = out.split(s)[0]
                    self.last_provider = "domo_ai"
                    return out
            except httpx.HTTPStatusError as hse:
                last_exc = hse
                code = hse.response.status_code
                logger.warning(f"Domo AI attempt {attempt + 1} HTTP {code}")
                if attempt < 2 and (code == 429 or code >= 500):
                    time.sleep(backoff_seconds[attempt])
                    continue
                self.last_provider = "failed"
                raise DomoAIUnavailableException(f"Domo AI generation request rejected: HTTP {code}")
            except httpx.TimeoutException as te:
                last_exc = te
                logger.warning(f"Domo AI attempt {attempt + 1} timed out")
                if attempt < 2:
                    time.sleep(backoff_seconds[attempt])
                    continue
                self.last_provider = "timeout"
                raise DomoAIUnavailableException("Domo AI generation request timed out after 45s.")
            except Exception as e:
                last_exc = e
                logger.warning(f"Domo AI attempt {attempt + 1} error: {type(e).__name__}")
                if attempt < 2:
                    time.sleep(backoff_seconds[attempt])
                    continue
                self.last_provider = "error"
                raise DomoAIUnavailableException(f"Domo AI generation communication failure: {type(e).__name__}")
        self.last_provider = "error"
        raise DomoAIUnavailableException(f"Domo AI generation communication failure: {type(last_exc).__name__}")

    def _simulate_response(self, prompt: str) -> str:
        """
        Deterministic fallback simulator for offline testing and development
        when Domo credentials are not configured or external service is unreachable.
        Inspects strictly the current USER QUESTION, never the past conversation history.
        """
        # Extract scratchpad if present
        scratchpad_part = ""
        if "SCRATCHPAD" in prompt:
            scratchpad_part = prompt.split("SCRATCHPAD")[-1]
            if "USER QUESTION:" in scratchpad_part:
                scratchpad_part = scratchpad_part.split("USER QUESTION:")[0]

        # Extract only the current user question
        current_question = prompt
        if "USER QUESTION:" in prompt:
            current_question = prompt.split("USER QUESTION:")[-1].split("Respond with ONE JSON object:")[0].strip()

        # If scratchpad already contains a tool result, formulate the final answer
        if "RESULT:" in scratchpad_part:
            m = re.findall(r"RESULT:\s*(\{.*?\}|\[.*?\]|.+?)(?=\nCALL|\nUSER|$)", scratchpad_part, re.DOTALL)
            last_result = m[-1] if m else "Order data retrieved."
            try:
                data = json.loads(last_result.strip())
                # Format based on tool output shape
                if "customer_order_id" in data and "delay_category" in data:
                    cid = data["customer_order_id"]
                    cat = data.get("delay_category", "UNKNOWN")
                    reasons = ", ".join(data.get("delay_reasons", [])) or "No delay reasons noted."
                    ans = (
                        f"### Order Delay Analysis: {cid}\n"
                        f"- **Customer**: {data.get('customer_name')}\n"
                        f"- **Product**: {data.get('product_name')}\n"
                        f"- **Operational Status**: {data.get('order_status')} (Risk Category: **{cat}**)\n"
                        f"- **Confirmed Delivery Date**: {data.get('confirmed_delivery_date')}\n"
                        f"- **Delay Root Cause**: {reasons}\n"
                        f"- **Transit Milestones Delayed**: {len(data.get('transit_delay_milestones', []))}\n\n"
                        f"**Source tables used**: fact_customer_order, fact_shipment_milestone, dim_customer\n"
                        f"**Next recommended action**: Review carrier milestone tracking and notify customer account representative."
                    )
                elif "customer_order_id" in data:
                    cid = data["customer_order_id"]
                    ans = (
                        f"### Customer Order Status: {cid}\n"
                        f"- **Customer**: {data.get('customer_name')}\n"
                        f"- **Product**: {data.get('product_name')}\n"
                        f"- **Status**: {data.get('order_status')}\n"
                        f"- **Confirmed Date**: {data.get('confirmed_delivery_date')}\n"
                        f"- **Ordered / Shipped**: {data.get('order_qty')} / {data.get('shipped_qty')} units\n"
                        f"- **Risk Level**: {data.get('risk_level')} ({data.get('risk_category')})\n\n"
                        f"**Source tables used**: fact_customer_order, dim_customer, dim_product\n"
                        f"**Next recommended action**: Monitor fulfillment progress against confirmed delivery date."
                    )
                elif "total_at_risk" in data:
                    ans = (
                        f"### At-Risk Orders Summary\n"
                        f"- **Total at-risk orders**: {data.get('total_at_risk')}\n"
                        f"- **Actual delayed**: {data.get('actual_delayed')}\n"
                        f"- **Potential delayed**: {data.get('potential_delayed')}\n"
                        f"- **Unknown risk (unlinked)**: {data.get('unknown_risk')}\n\n"
                        f"**Source tables used**: fact_customer_order, fact_shipment_milestone\n"
                        f"**Next recommended action**: Prioritize overdue orders with confirmed past delivery dates."
                    )
                elif "customer_id" in data and "customer_name" in data:
                    cname = data.get("customer_name")
                    ans = (
                        f"### Customer Order Summary: {cname} ({data.get('customer_id')})\n"
                        f"- **Segment**: {data.get('segment')} ({data.get('country')})\n"
                        f"- **Service Level**: {data.get('service_level')}\n"
                        f"- **Total Orders**: {data.get('total_orders')} (Delivered: {data.get('delivered_orders')}, Open: {data.get('open_orders')})\n"
                        f"- **Fulfillment Rate**: {data.get('fulfillment_rate_pct')}%\n"
                        f"- **Total Order Value**: INR {data.get('total_order_value_inr', 0):,.2f}\n\n"
                        f"**Source tables used**: dim_customer, fact_customer_order\n"
                        f"**Next recommended action**: Review open orders for fulfillment scheduling."
                    )
                elif "error" in data:
                    ans = f"Operational alert: {data['error']}\n\n**Source tables used**: dim_customer, fact_customer_order\n**Next recommended action**: Check identifier and retry with valid record ID."
                else:
                    ans = f"Based on system records: {last_result.strip()[:400]}"
            except Exception:
                ans = f"Based on system records: {last_result.strip()[:400]}"

            return json.dumps({"action": "final", "answer": ans})

        # Tool selection from CURRENT QUESTION ONLY
        lower = current_question.lower()

        # Check for order ID in the current question
        order_match = re.search(r"\bco-\d{5,6}\b", lower)
        if not order_match:
            order_match = re.search(r"\bco-[a-z0-9-]+\b", lower)

        # Check for customer name or ID in current question
        cust_match = re.search(r"\bcus-\d{3}\b", lower)
        has_cust_intent = any(w in lower for w in ["customer", "summarize", "summary", "account", "profile"])
        for known_name in ["digital bazaar", "retailer north", "mobilemart", "global devices"]:
            if known_name in lower:
                return json.dumps({
                    "action": "get_customer_summary",
                    "input": {"customer_id": known_name.title()}
                })

        if cust_match:
            return json.dumps({
                "action": "get_customer_summary",
                "input": {"customer_id": cust_match.group(0).upper()}
            })

        # Order-specific questions
        if order_match:
            order_id = order_match.group(0).upper()
            is_delay_or_shipment = any(w in lower for w in [
                "delay", "why", "root cause", "shipment", "transit", "carrier", "quality", "hold", "inspection"
            ])
            if is_delay_or_shipment:
                return json.dumps({
                    "action": "get_order_delay_analysis",
                    "input": {"customer_order_id": order_id}
                })
            else:
                return json.dumps({
                    "action": "get_order_status",
                    "input": {"customer_order_id": order_id}
                })

        # At risk orders
        if any(w in lower for w in ["at risk", "at-risk", "delayed orders", "delays", "critical orders"]):
            risk_type = "ACTUAL_DELAY" if "actual" in lower else None
            return json.dumps({
                "action": "list_at_risk_orders",
                "input": {"limit": 10, "risk_type": risk_type}
            })

        # Customer summary without explicit name (fallback)
        if has_cust_intent and ("cus-" in lower or "retailer" in lower):
            return json.dumps({
                "action": "get_customer_summary",
                "input": {"customer_id": "CUS-001"}
            })

        return json.dumps({
            "action": "final",
            "answer": "Hello! I am your Customer Order Management AI Agent. I can help you check order statuses (e.g. CO-000001), analyze delay root causes, inspect carrier shipment milestones, list at-risk orders, and summarize customer accounts. Please provide an Order ID (CO-XXXXXX) or Customer Name to begin."
        })


def call_domo_llm(
    prompt: str,
    temperature: float = 0.1,
    max_tokens: int = 1500,
    system: Optional[str] = None,
) -> Tuple[Optional[str], str]:
    """Helper to invoke DomoTextLLM directly with error handling."""
    llm = DomoTextLLM(temperature=temperature, max_tokens=max_tokens, system=system)
    try:
        out = llm.invoke(prompt)
        return out, getattr(llm, "last_provider", "domo_ai")
    except Exception as e:
        return None, "error"


