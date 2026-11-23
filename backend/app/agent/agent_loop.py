import json
import re
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from langchain_core.output_parsers import StrOutputParser

from .domo_client import DomoTextLLM, DomoAIUnavailableException, is_domo_configured
from .tools import AVAILABLE_TOOLS, TOOL_DESCRIPTIONS, resolve_customer
from .prompts import AGENT_SYSTEM_PROMPT, AGENT_USER_PROMPT_TEMPLATE
from ..schemas.chat import DomoActionDecision, DomoAgentFinalResult, ToolStep
from ..repositories.audit_repo import AuditRepository


def _clean_final_answer(answer: Any) -> str:
    """Ensure the final answer is clean human-readable text, stripping any raw JSON envelope or thoughts."""
    if not answer:
        return ""
    if not isinstance(answer, str):
        if isinstance(answer, dict):
            return answer.get("answer") or answer.get("response") or str(answer)
        return str(answer)

    s = answer.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s).strip()

    # If it's a JSON string or looks like a dict with thought/action/answer
    if (s.startswith("{") and s.endswith("}")) or ('"thought"' in s and '"answer"' in s):
        try:
            parsed = json.loads(s, strict=False)
            if isinstance(parsed, dict):
                ans = parsed.get("answer") or parsed.get("response") or parsed.get("final_answer")
                if ans and isinstance(ans, str):
                    return _clean_final_answer(ans)
        except Exception:
            pass

        # Robust regex extraction if json.loads failed
        # 1. Match "answer": "..." with unicode/escapes
        m = re.search(r'"(?:answer|response|final_answer)"\s*:\s*"((?:[^"\\]|\\.)*)"', s, re.DOTALL)
        if m:
            raw_val = m.group(1)
            try:
                return json.loads(f'"{raw_val}"')
            except Exception:
                return raw_val.replace('\\n', '\n').replace('\\"', '"').replace('\\t', '\t')

        # 2. Match unclosed or multiline "answer": "
        m2 = re.search(r'"(?:answer|response|final_answer)"\s*:\s*"(.*)', s, re.DOTALL)
        if m2:
            tail = m2.group(1).rstrip('"} \n\r\t')
            return tail.replace('\\n', '\n').replace('\\"', '"').replace('\\t', '\t')

    return s


def repair_truncated_json(text: str) -> str:
    """Salvage truncated or slightly malformed JSON by balancing brackets, braces, and quotes."""
    if not text:
        return ""
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s).strip()

    m = re.search(r"\{.*", s, re.DOTALL)
    if not m:
        return s
    candidate = m.group(0).strip()

    try:
        json.loads(candidate)
        return candidate
    except Exception:
        pass

    clean = candidate
    in_quote = False
    escape = False
    for char in clean:
        if escape:
            escape = False
        elif char == '\\':
            escape = True
        elif char == '"':
            in_quote = not in_quote

    if in_quote:
        clean += '"'

    open_brackets = []
    in_q = False
    esc = False
    for char in clean:
        if esc:
            esc = False
        elif char == '\\':
            esc = True
        elif char == '"':
            in_q = not in_q
        elif not in_q:
            if char in '{[':
                open_brackets.append(char)
            elif char in '}]':
                if open_brackets:
                    if (char == '}' and open_brackets[-1] == '{') or (char == ']' and open_brackets[-1] == '['):
                        open_brackets.pop()

    for b in reversed(open_brackets):
        if b == '{':
            clean += '}'
        elif b == '[':
            clean += ']'

    try:
        json.loads(clean)
        return clean
    except Exception:
        clean_no_comma = re.sub(r",\s*([\}\]])", r"\1", clean)
        try:
            json.loads(clean_no_comma)
            return clean_no_comma
        except Exception:
            return candidate


def _normalize_dict_keys(d: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize dictionary keys (unwrap common wrappers and lowercase aliases)."""
    if not isinstance(d, dict):
        return d
    # If the dictionary is wrapped inside a single wrapper key
    for wrapper in ["final_answer", "decision", "result", "feasibility_assessment", "monitoring_result"]:
        if wrapper in d and isinstance(d[wrapper], dict) and len(d) <= 3:
            sub = d.pop(wrapper)
            d.update(sub)

    normalized: Dict[str, Any] = {}
    for k, v in d.items():
        k_clean = str(k).strip()
        k_lower = k_clean.lower()
        if k_lower in ("overall_status", "status", "feasibility_status"):
            normalized["overall_status"] = v
        elif k_lower in ("estimated_delivery_date", "promise_date", "achievable_date", "delivery_date"):
            normalized["estimated_delivery_date"] = v
        elif k_lower in ("per_department_days", "department_days", "lead_times"):
            normalized["per_department_days"] = v
        elif k_lower in ("corrective_actions", "actions", "mitigations"):
            normalized["corrective_actions"] = v
        elif k_lower in ("proposal_reasons", "reasons"):
            normalized["proposal_reasons"] = v
        elif k_lower in ("blockers", "blocker_summary"):
            normalized["blockers"] = v
        elif k_lower in ("risks", "active_risks", "detected_risks"):
            normalized["risks"] = v
        else:
            normalized[k_clean] = v
    return normalized


def _extract_json(text: str) -> dict:
    """Extract and parse JSON object from model output with tolerant repairs and wrapper unwrapping."""
    if not text:
        return {"action": "final", "answer": ""}
    clean = text.strip()
    # Strip markdown fences if present
    if clean.startswith("```"):
        clean = re.sub(r"^```[a-zA-Z]*\n?", "", clean)
        clean = re.sub(r"\n?```$", "", clean).strip()

    # Find outermost matching braces
    m = re.search(r"\{.*\}", clean, re.DOTALL)
    candidate = m.group(0) if m else clean

    # 1. Try strict=False first
    try:
        data = json.loads(candidate, strict=False)
        if isinstance(data, dict):
            data = _normalize_dict_keys(data)
            # If answer itself is a valid JSON string containing top-level fields, unwrap it
            if isinstance(data.get("answer"), str):
                ans_str = data["answer"].strip()
                if ans_str.startswith("{") and ans_str.endswith("}"):
                    try:
                        ans_dict = json.loads(ans_str)
                        if isinstance(ans_dict, dict):
                            ans_norm = _normalize_dict_keys(ans_dict)
                            for k, v in ans_norm.items():
                                if k not in data or data[k] is None:
                                    data[k] = v
                    except Exception:
                        pass
                else:
                    data["answer"] = _clean_final_answer(data["answer"])
            return data
    except Exception:
        pass

    # 2. Try JSON repair for truncated output
    repaired = repair_truncated_json(clean)
    try:
        data = json.loads(repaired, strict=False)
        if isinstance(data, dict):
            data = _normalize_dict_keys(data)
            return data
    except Exception:
        pass

    # 3. Regex extraction for standard keys
    action_m = re.search(r'"action"\s*:\s*"([^"]+)"', clean, re.IGNORECASE)
    thought_m = re.search(r'"thought"\s*:\s*"((?:[^"\\]|\\.)*)"', clean, re.DOTALL | re.IGNORECASE)

    extracted_action = action_m.group(1) if action_m else None
    extracted_thought = thought_m.group(1) if thought_m else None

    # Try extracting answer
    extracted_answer = None
    ans_m = re.search(r'"(?:answer|response|final_answer)"\s*:\s*"((?:[^"\\]|\\.)*)"', clean, re.DOTALL)
    if ans_m:
        raw_val = ans_m.group(1)
        try:
            extracted_answer = json.loads(f'"{raw_val}"')
        except Exception:
            extracted_answer = raw_val.replace('\\n', '\n').replace('\\"', '"')
    elif '"answer"' in clean:
        parts = clean.split('"answer"', 1)
        m_after = re.search(r':\s*"?(.*)', parts[1], re.DOTALL)
        if m_after:
            extracted_answer = m_after.group(1).rstrip('"} \n\r\t').replace('\\n', '\n').replace('\\"', '"')

    # If action was extracted and it's a tool call
    if extracted_action and extracted_action.lower() != "final":
        input_dict = {}
        inp_m = re.search(r'"input"\s*:\s*(\{.*?\})', clean, re.DOTALL)
        if inp_m:
            try:
                input_dict = json.loads(inp_m.group(1), strict=False)
            except Exception:
                pass
        return {
            "action": extracted_action,
            "thought": extracted_thought,
            "input": input_dict,
            "answer": extracted_answer,
        }

    # Extract other key fields that might be present in clean text
    out: Dict[str, Any] = {
        "action": "final",
        "thought": extracted_thought,
        "answer": _clean_final_answer(extracted_answer) if extracted_answer else _clean_final_answer(clean),
    }

    stat_m = re.search(r'"(?:overall_status|status)"\s*:\s*"([^"]+)"', clean, re.IGNORECASE)
    if stat_m:
        out["overall_status"] = stat_m.group(1).upper().strip()

    date_m = re.search(r'"(?:estimated_delivery_date|promise_date)"\s*:\s*"([^"]+)"', clean, re.IGNORECASE)
    if date_m:
        out["estimated_delivery_date"] = date_m.group(1).strip()

    return _normalize_dict_keys(out)


def extract_order_id(text: str) -> Optional[str]:
    """Extract explicit customer order ID (e.g. CO-000001, CO-PROMISE-1) from text."""
    if not text:
        return None
    # Standard format: CO-000001 (6 digits) or CO-10002 (5 digits)
    m = re.search(r"\b(CO-\d{5,6})\b", text, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # Generic format: CO-XXXX
    m = re.search(r"\b(CO-[A-Za-z0-9-]+)\b", text, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return None


def extract_previous_order_id(history: List[Dict[str, str]]) -> Optional[str]:
    """Find the most recently discussed customer order ID in conversation history."""
    for msg in reversed(history or []):
        content = msg.get("content", "")
        oid = extract_order_id(content)
        if oid:
            return oid
    return None


def is_explicit_order_follow_up(text: str) -> bool:
    """Check if the user explicitly refers to a previously discussed order."""
    lower = text.lower()
    patterns = [
        r"\b(that order|this order|the order|same order|previous order)\b",
        r"\b(its status|its delivery|its shipment|its delay|its timeline|its progress|its quality)\b",
        r"\b(why was it|why is it|where is it|when will it|is it delayed|is it shipped|is it delivered)\b",
        r"^(what about it|and that|status of it|details of it)\b",
    ]
    return any(re.search(p, lower) for p in patterns)


def route_supported_intent(
    db: Session,
    question: str,
    history: List[Dict[str, str]],
) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """
    Deterministic intent router for supported manufacturing agent queries.
    Returns: (tool_name, tool_input, clarification_message)
    """
    q_lower = question.lower().strip()

    # -------------------------------------------------------------------------
    # 1. Customer Summary Intent
    # -------------------------------------------------------------------------
    cust_keywords = ["customer", "summarize", "summary", "account", "profile", "performing", "performance"]
    has_cust_intent = any(k in q_lower for k in cust_keywords)
    
    # Check for customer in question dynamically against DimCustomer in database
    from ..models.business import DimCustomer
    customer_match = None
    all_customers = db.query(DimCustomer.customer_id, DimCustomer.customer_name).all()
    for cid, cname in all_customers:
        if cname and cname.lower() in q_lower:
            customer_match = cid
            break
        if cid and cid.lower() in q_lower:
            customer_match = cid
            break

    if not customer_match:
        cus_id_match = re.search(r"\b(cus-[a-zA-Z0-9-]+)\b", q_lower)
        if cus_id_match:
            customer_match = cus_id_match.group(1).upper()

    if customer_match:
        cust = resolve_customer(db, customer_match)
        cid = cust.customer_id if cust else customer_match
        return "get_customer_summary", {"customer_id": cid}, None

    if has_cust_intent and not extract_order_id(question) and not any(k in q_lower for k in ["at risk", "at-risk", "delayed orders"]):
        # Ambiguous customer request without specifying customer name
        sample_names = ", ".join([f"{cname} ({cid})" for cid, cname in all_customers[:4]])
        return None, None, (
            f"Which customer would you like me to summarize? "
            f"Please specify a customer account, for example: {sample_names}."
        )

    # -------------------------------------------------------------------------
    # 2. At-Risk Orders Intent
    # -------------------------------------------------------------------------
    at_risk_keywords = [
        "at risk", "at-risk", "delayed orders", "which orders are delayed",
        "what orders are delayed", "orders at risk", "risk summary", "list delays",
        "critical orders", "potential delay", "unlinked orders", "unknown risk",
    ]
    is_at_risk_query = any(k in q_lower for k in at_risk_keywords)
    current_order_id = extract_order_id(question)

    if is_at_risk_query and not current_order_id:
        # Parse optional limit
        limit = 10
        limit_m = re.search(r"\b(\d+)\s*orders?\b", q_lower)
        if limit_m:
            try:
                limit = int(limit_m.group(1))
            except ValueError:
                limit = 10
        # Parse optional risk category filter
        risk_type = None
        if "actual" in q_lower:
            risk_type = "ACTUAL_DELAY"
        elif "potential" in q_lower:
            risk_type = "POTENTIAL_DELAY"
        elif "unknown" in q_lower:
            risk_type = "UNKNOWN_RISK"

        return "list_at_risk_orders", {"limit": limit, "risk_type": risk_type}, None

    # -------------------------------------------------------------------------
    # 3. Order-Specific Query (Status, Delay, Shipment, Quality)
    # -------------------------------------------------------------------------
    target_order_id = current_order_id

    # If no order ID in current question, check if it's an explicit follow-up
    if not target_order_id:
        if is_explicit_order_follow_up(question):
            target_order_id = extract_previous_order_id(history)
            if not target_order_id:
                return None, None, "Please specify the Customer Order ID (e.g. CO-000001) you would like to inspect."
        elif any(k in q_lower for k in ["my order", "the order status", "order status", "why is the order", "check order"]):
            # Missing order identifier
            return None, None, "Please specify the Customer Order ID (e.g. CO-000001) you would like to check."

    if target_order_id:
        # Determine whether it's delay/shipment/quality investigation OR general status
        delay_shipment_quality_keywords = [
            "delay", "delayed", "why", "root cause", "late", "slip", "transit",
            "shipment", "shipping", "carrier", "milestone", "freight", "air cargo",
            "tracking", "quality", "inspection", "defect", "hold", "disposition",
            "rework", "scrap", "discrepancy"
        ]
        is_investigation = any(k in q_lower for k in delay_shipment_quality_keywords)

        if is_investigation:
            return "get_order_delay_analysis", {"customer_order_id": target_order_id}, None
        else:
            return "get_order_status", {"customer_order_id": target_order_id}, None

    # No deterministic pattern matched; allow Domo LLM to reason
    return None, None, None


def _format_deterministic_answer(tool_name: str, tool_input: Dict[str, Any], data: Dict[str, Any]) -> str:
    """Format structured, verified markdown answer directly from tool output."""
    if "error" in data:
        return (
            f"### Operational Notice\n"
            f"**Result**: {data['error']}\n\n"
            f"**Source tables used**: dim_customer, fact_customer_order\n"
            f"**Next recommended action**: Verify the record identifier and retry with an active customer or order ID."
        )

    if tool_name == "get_order_status":
        cid = data.get("customer_order_id")
        return (
            f"### Customer Order Status: {cid}\n"
            f"- **Customer**: {data.get('customer_name')}\n"
            f"- **Product**: {data.get('product_name')}\n"
            f"- **Status**: `{data.get('order_status')}` (Priority: {data.get('priority')})\n"
            f"- **Order Date**: {data.get('order_date')}\n"
            f"- **Confirmed Delivery Date**: {data.get('confirmed_delivery_date')}\n"
            f"- **Order Quantity**: {data.get('order_qty')} units (Shipped: {data.get('shipped_qty')} units)\n"
            f"- **Total Order Value**: INR {data.get('total_value_inr', 0):,.2f}\n"
            f"- **Operational Risk Level**: **{data.get('risk_level')}** (Category: `{data.get('risk_category')}`)\n"
            f"- **Active Shipments**: {data.get('shipment_count')} shipment milestone(s)\n\n"
            f"**Source tables used**: fact_customer_order, dim_customer, dim_product, fact_shipment_milestone\n"
            f"**Next recommended action**: Review order progress against confirmed delivery date and monitor fulfillment."
        )

    if tool_name == "get_order_delay_analysis":
        cid = data.get("customer_order_id")
        reasons = "\n".join(f"- {r}" for r in data.get("delay_reasons", [])) or "- No delay reasons recorded."
        warnings = "\n".join(f"- {w}" for w in data.get("data_quality_warnings", []))
        
        milestones = data.get("transit_delay_milestones", [])
        milestone_str = ""
        if milestones:
            milestone_str = "\n**Delayed Transit Milestones**:\n" + "\n".join(
                f"- Shipment `{m.get('shipment_id')}` via {m.get('carrier')} ({m.get('vehicle_type')}): Status `{m.get('shipment_status')}`"
                for m in milestones
            )

        quality_str = ""
        if data.get("quality_notes"):
            quality_str = "\n**Quality Inspection Notes**:\n" + "\n".join(f"- {q}" for q in data.get("quality_notes"))

        qty_match_str = "Verified match" if data.get("quantity_match") else f"Mismatch ({data.get('shipped_qty')}/{data.get('order_qty')})"

        return (
            f"### Order Delay & Transit Analysis: {cid}\n"
            f"- **Customer**: {data.get('customer_name')}\n"
            f"- **Product**: {data.get('product_name')}\n"
            f"- **Operational Status**: `{data.get('order_status')}` (Risk Category: **{data.get('delay_category')}**)\n"
            f"- **Confirmed Delivery Date**: {data.get('confirmed_delivery_date')}\n"
            f"- **Quantity Match**: {qty_match_str}\n\n"
            f"**Root Cause Delay Factors**:\n{reasons}\n"
            f"{milestone_str}"
            f"{quality_str}\n"
            f"{'**Data Quality Warnings**:\n' + warnings if warnings else ''}\n\n"
            f"**Source tables used**: fact_customer_order, fact_shipment_milestone, fact_production_order, fact_quality_inspection\n"
            f"**Next recommended action**: Escalate carrier delays to logistics coordinator and inspect production hold status."
        )

    if tool_name == "list_at_risk_orders":
        total = data.get("total_at_risk", 0)
        actual = data.get("actual_delayed", 0)
        potential = data.get("potential_delayed", 0)
        unknown = data.get("unknown_risk", 0)
        orders = data.get("orders", [])
        
        order_rows = []
        for o in orders[:5]:
            reasons_preview = "; ".join(o.get("reasons", [])[:1])
            order_rows.append(
                f"- **{o.get('customer_order_id')}** ({o.get('customer_name')}): `{o.get('risk_category')}` - Confirmed: {o.get('confirmed_delivery_date')} - {reasons_preview}"
            )
        orders_str = "\n".join(order_rows)

        return (
            f"### Operational At-Risk Orders Summary\n"
            f"- **Total at-risk orders**: {total}\n"
            f"- **Actual delayed**: {actual} orders\n"
            f"- **Potential delayed**: {potential} orders\n"
            f"- **Unknown risk (unlinked production)**: {unknown} orders\n\n"
            f"**Key At-Risk Orders Sample**:\n{orders_str}\n\n"
            f"**Source tables used**: fact_customer_order, fact_shipment_milestone, fact_production_order\n"
            f"**Next recommended action**: Prioritize critical overdue orders with confirmed dates in the past."
        )

    if tool_name == "get_customer_summary":
        cname = data.get("customer_name")
        cid = data.get("customer_id")
        return (
            f"### Customer Order Summary: {cname} ({cid})\n"
            f"- **Segment / Country**: {data.get('segment')} ({data.get('country')})\n"
            f"- **Service Level**: `{data.get('service_level')}` (Preferred Carrier: {data.get('preferred_carrier')})\n"
            f"- **Total Orders**: {data.get('total_orders')} orders\n"
            f"- **Delivered Orders**: {data.get('delivered_orders')}\n"
            f"- **Open / Active Orders**: {data.get('open_orders')}\n"
            f"- **Fulfillment Rate**: **{data.get('fulfillment_rate_pct')}%**\n"
            f"- **Total Order Value**: INR {data.get('total_order_value_inr', 0):,.2f}\n\n"
            f"**Source tables used**: dim_customer, fact_customer_order\n"
            f"**Next recommended action**: Review open orders with account manager to guarantee service-level agreement adherence."
        )

    return f"Verified system output: {json.dumps(data, default=str)}"


def run_agent_loop(
    db: Session,
    question: str,
    history: Optional[List[Dict[str, str]]] = None,
    max_steps: int = 5,
    user_id: Optional[int] = None,
    system_prompt_template: Optional[str] = None,
    user_prompt_template: Optional[Any] = None,
    tools: Optional[Dict[str, Any]] = None,
    tool_descriptions: Optional[str] = None,
    audit_entity: str = "agent_tool",
    enable_deterministic_fallback: bool = True,
    max_tokens: int = 900,
    temperature: float = 0.1,
    llm_call_counter: Optional[List[int]] = None,
    max_llm_calls: Optional[int] = None,
    return_dict: bool = False,
    tool_context: Optional[Dict[str, Any]] = None,
    step_callback: Optional[Any] = None,
) -> Tuple[Any, List[Dict[str, Any]], str, bool]:
    """
    Executes Domo AI-driven ReAct loop:
    1. Runs system prompt with rules, constraints, and tool descriptions.
    2. Domo decides which appropriate tool to call.
    3. Tool executes against the operational database.
    4. Observation is evaluated (checked whether it gave the correct result, or if a different tool is needed).
    5. If more data is needed, Domo is called again with the updated scratchpad and system prompt.
    6. When Domo finishes, the response is parsed and validated using Pydantic schemas.
    7. Returns answer and steps to be stored in the DB and displayed in the UI.
    """
    active_tools = tools if tools is not None else AVAILABLE_TOOLS
    active_tool_descriptions = tool_descriptions if tool_descriptions is not None else TOOL_DESCRIPTIONS
    active_system_prompt_template = system_prompt_template if system_prompt_template is not None else AGENT_SYSTEM_PROMPT
    active_user_prompt_template = user_prompt_template if user_prompt_template is not None else AGENT_USER_PROMPT_TEMPLATE

    # --------------------------------------------------------------------------
    # 1. LIVE DOMO AI REACT AGENT WORKFLOW
    # --------------------------------------------------------------------------
    if is_domo_configured():
        system_prompt = active_system_prompt_template.format(tools=active_tool_descriptions)
        llm = DomoTextLLM(max_tokens=max_tokens, temperature=temperature)

        history_str = "\n".join(
            f"{m.get('role', 'user').upper()}: {m.get('content', '')}"
            for m in (history or [])[-6:]
        ) if history else "(No prior conversation)"

        scratchpad = ""
        steps: List[Dict[str, Any]] = []

        for step_num in range(max_steps):
            if max_llm_calls is not None and llm_call_counter is not None and llm_call_counter[0] >= max_llm_calls:
                return (
                    ({"action": "final", "answer": "LLM call limit reached", "risks": []} if return_dict else "LLM call limit reached"),
                    steps,
                    "llm_limit_reached",
                    False,
                )

            rendered_prompt = active_user_prompt_template.format(
                system_prompt=system_prompt,
                history=history_str,
                scratchpad=scratchpad if scratchpad else "(No tool calls yet)",
                question=question,
            )

            try:
                if llm_call_counter is not None:
                    llm_call_counter[0] += 1
                raw_response = llm.invoke(rendered_prompt)
            except DomoAIUnavailableException as dae:
                return (
                    ({"action": "final", "answer": f"**Domo AI Service Notice**: {str(dae)}", "risks": []} if return_dict else f"**Domo AI Service Notice**: {str(dae)}"),
                    steps,
                    "ai_unavailable",
                    False,
                )
            except Exception as e:
                return (
                    ({"action": "final", "answer": f"Error communicating with AI service: {str(e)}", "risks": []} if return_dict else f"Error communicating with AI service: {str(e)}"),
                    steps,
                    "error",
                    False,
                )

            action_dict = _extract_json(raw_response)
            
            # Pydantic structured output validation
            extracted_ans = (
                action_dict.get("answer")
                or action_dict.get("response")
                or action_dict.get("content")
                or action_dict.get("text")
                or action_dict.get("final_answer")
                or action_dict.get("summary")
            )
            # If extracted answer is still None but action is final, look inside thought or parse recursively
            if not extracted_ans and action_dict.get("action") == "final":
                extracted_ans = action_dict.get("thought") or raw_response

            # If extracted answer itself looks like JSON or contains raw thoughts/envelopes, clean it
            extracted_ans = _clean_final_answer(extracted_ans)

            try:
                decision = DomoActionDecision.model_validate({
                    "action": action_dict.get("action") or ("final" if extracted_ans else "get_order_status"),
                    "thought": action_dict.get("thought"),
                    "input": action_dict.get("input", {}),
                    "answer": extracted_ans,
                    "source_tables": action_dict.get("source_tables", []),
                    "recommended_action": action_dict.get("recommended_action"),
                    "confidence": action_dict.get("confidence", "HIGH"),
                })
            except Exception:
                decision = DomoActionDecision(
                    action=action_dict.get("action", "final"),
                    thought=action_dict.get("thought"),
                    input=action_dict.get("input", {}),
                    answer=extracted_ans or _clean_final_answer(raw_response),
                )

            # Check if Domo delivered the final answer
            if decision.action == "final" and decision.answer:
                try:
                    AuditRepository.log(
                        db=db,
                        action="AGENT_FINAL",
                        entity=audit_entity,
                        entity_id="final",
                        user_id=user_id,
                        payload={
                            "thought": decision.thought or action_dict.get("thought"),
                            "action": "final",
                            "confidence": action_dict.get("confidence", "HIGH"),
                            "risks_count": len(action_dict.get("risks", [])) if isinstance(action_dict.get("risks"), list) else 0,
                            "answer": str(action_dict.get("answer"))[:500],
                        },
                    )
                except Exception:
                    pass

                if return_dict:
                    return action_dict, steps, "domo_ai", True

                clean_final_text = _clean_final_answer(decision.answer)
                final_validated = DomoAgentFinalResult(
                    answer=clean_final_text,
                    steps=[ToolStep.model_validate(s) for s in steps],
                    provider="domo_ai",
                    ai_available=True,
                    confidence=decision.confidence or "HIGH",
                    source_tables=decision.source_tables or [],
                    recommended_action=decision.recommended_action,
                )
                return final_validated.answer, steps, "domo_ai", True

            # Domo called an operational tool
            tool_name = decision.action
            tool_func = active_tools.get(tool_name)
            if not tool_func:
                err_msg = f"Unknown tool '{tool_name}'. Approved tools: {list(active_tools.keys())}"
                scratchpad += f"\n[Step {step_num + 1}] System check: {err_msg}\n"
                continue

            tool_input = decision.input or {}
            if not isinstance(tool_input, dict):
                tool_input = {}

            # Sanitize tool input against immutable tool_context (server-side verified truth)
            call_kwargs = dict(tool_input)
            if tool_context and isinstance(tool_context, dict):
                for ctx_key in (
                    "customer_id",
                    "product_id",
                    "order_qty",
                    "requested_delivery_date",
                    "unit_price_inr",
                    "priority",
                    "channel",
                    "ship_to",
                ):
                    if ctx_key in tool_context and tool_context[ctx_key] is not None:
                        if ctx_key in call_kwargs and str(call_kwargs[ctx_key]) != str(tool_context[ctx_key]):
                            logger.warning(
                                "Agent model supplied %s=%r conflicting with verified context=%r; enforcing server context.",
                                ctx_key,
                                call_kwargs[ctx_key],
                                tool_context[ctx_key],
                            )
                        # Always ensure immutable server context wins
                        call_kwargs[ctx_key] = tool_context[ctx_key]

            # Execute tool against PostgreSQL / SQLite database
            try:
                import inspect
                sig = inspect.signature(tool_func)
                # Auto-inject order_context dictionary if accepted
                if "order_context" in sig.parameters:
                    call_kwargs["order_context"] = tool_context
                # Inject missing parameters from tool_context if accepted by tool function
                if tool_context and isinstance(tool_context, dict):
                    for p_name in sig.parameters:
                        if p_name in tool_context and p_name not in call_kwargs:
                            call_kwargs[p_name] = tool_context[p_name]

                obs = tool_func(db=db, **call_kwargs)
            except TypeError as te:
                obs = {"error": f"Invalid arguments for {tool_name}: {str(te)}"}
            except Exception as ex:
                obs = {"error": f"Tool execution failed: {str(ex)}"}

            # Check observation (whether it gave correct result or needs different tool)
            has_error = bool("error" in obs)
            is_empty = bool(obs.get("total", 1) == 0 or not obs)
            
            if has_error:
                eval_note = f"Observation check: Tool returned an error: {obs.get('error')}. Evaluate if a different tool or parameters are needed."
            elif is_empty:
                eval_note = "Observation check: No records found. Evaluate if another tool or broader query should be used."
            else:
                eval_note = "Observation check: Database facts retrieved successfully."

            logged_input = dict(call_kwargs)
            if isinstance(logged_input.get("order_context"), dict):
                logged_ctx = {k: v for k, v in logged_input["order_context"].items() if k != "precomputed_readiness"}
                logged_input["order_context"] = logged_ctx

            step_record = {
                "step": step_num + 1,
                "tool": tool_name,
                "input": logged_input,
                "output": obs,
                "thought": decision.thought,
                "status": "error" if has_error else "success",
            }
            steps.append(step_record)
            if step_callback is not None:
                try:
                    step_callback(step_record)
                except Exception:
                    pass

            try:
                AuditRepository.log(
                    db=db,
                    action="TOOL_CALL",
                    entity=audit_entity,
                    entity_id=tool_name,
                    user_id=user_id,
                    payload={"thought": decision.thought, "tool": tool_name, "input": tool_input, "output": obs},
                )
            except Exception:
                pass

            obs_str = json.dumps(obs, default=str)
            if len(obs_str) > 6000:
                obs_str = obs_str[:6000] + "... [truncated]"

            scratchpad += (
                f"\nStep {step_num + 1}:\n"
                f"Thought: {decision.thought or 'Selected tool based on system prompt rules'}\n"
                f"Action: {tool_name}\n"
                f"Input: {json.dumps(tool_input)}\n"
                f"Observation: {obs_str}\n"
                f"Check: {eval_note}\n"
            )

        # Max steps reached: prompt Domo to synthesize all collected observations
        synth_prompt = (
            f"SYSTEM:\n{system_prompt}\n\n"
            f"USER QUESTION: {question}\n\n"
            f"OBSERVATIONS GATHERED ACROSS TURNS:\n{scratchpad}\n\n"
            f"Please synthesize the above verified observations into the final markdown response. "
            f"Respond with JSON format: {{\"action\": \"final\", \"answer\": \"...\"}}"
        )
        try:
            if max_llm_calls is None or llm_call_counter is None or llm_call_counter[0] < max_llm_calls:
                if llm_call_counter is not None:
                    llm_call_counter[0] += 1
                raw_synth = llm.invoke(synth_prompt)
                synth_dict = _extract_json(raw_synth)
                if return_dict:
                    return synth_dict, steps, "domo_ai", True
                if synth_dict.get("answer"):
                    return synth_dict["answer"], steps, "domo_ai", True
        except Exception:
            pass

        if return_dict:
            return {"action": "final", "answer": scratchpad[-500:], "risks": []}, steps, "domo_ai", True

        return (
            "I analyzed the order records but reached the maximum allowed analysis steps. "
            "Here is the verified operational data gathered:\n\n" + scratchpad[-500:],
            steps,
            "domo_ai",
            True,
        )

    # --------------------------------------------------------------------------
    # 2. DETERMINISTIC FALLBACK (WHEN DOMO AI IS UNCONFIGURED)
    # --------------------------------------------------------------------------
    if not enable_deterministic_fallback:
        return (
            ({"action": "final", "answer": "Domo AI unconfigured", "risks": []} if return_dict else "Domo AI unconfigured"),
            [],
            "ai_unavailable",
            False,
        )

    routed_tool, routed_input, clarification = route_supported_intent(db, question, history)

    if clarification:
        return clarification, [], "system", False

    if routed_tool:
        tool_func = AVAILABLE_TOOLS.get(routed_tool)
        if tool_func:
            try:
                obs = tool_func(db=db, **routed_input)
            except Exception as e:
                obs = {"error": f"Tool execution failed: {str(e)}"}

            steps = [{
                "step": 1,
                "tool": routed_tool,
                "input": routed_input,
                "output": obs,
                "thought": "Deterministic intent match",
                "status": "success",
            }]

            try:
                AuditRepository.log(
                    db=db,
                    action="TOOL_CALL",
                    entity="agent_tool",
                    entity_id=routed_tool,
                    user_id=user_id,
                    payload={"tool": routed_tool, "input": routed_input, "output": obs},
                )
            except Exception:
                pass

            deterministic_ans = _format_deterministic_answer(routed_tool, routed_input, obs)
            return deterministic_ans, steps, "deterministic_tool", False

    return (
        "**Operational AI Notice**: External Domo AI natural language model is currently unconfigured. "
        "However, direct operational queries are fully functional.\n\n"
        "You can query: \n"
        "- Specific order status: `CO-000001`\n"
        "- Root cause delay analysis: `Why is CO-000001 delayed?`\n"
        "- Customer summaries: `Digital Bazaar` or `Retailer North`\n"
        "- At-risk & delayed commitments: `Which orders are delayed?`",
        [],
        "ai_unavailable",
        False,
    )

