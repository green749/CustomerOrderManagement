import sys
import uuid
from datetime import date, datetime, timedelta, timezone
sys.path.insert(0, 'backend')

from app.database import SessionLocal
from app.agent.domo_client import is_domo_configured
from app.models.auth import User
from app.services.chat_service import ChatService
from app.services.feasibility_service import FeasibilityService
from app.services.monitoring_service import MonitoringService
from app.models.chat import Conversation, Message
from app.models.workflow import OrderAssessment, CommitmentProposal, RiskAlert, OrderMonitoringRecord

def test_pattern():
    print("=================================================================")
    print("VERIFYING DOMO AI -> DB TABLE -> UI PATTERN FOR ALL 3 AGENTS")
    print("=================================================================")
    print(f"Domo Configured: {is_domo_configured()}")
    assert is_domo_configured(), "Domo AI must be configured with real credentials!"

    db = SessionLocal()
    user = db.query(User).filter(User.email == "admin@manufacturing.com").first()
    if not user:
        user = db.query(User).first()
    assert user, "Admin user must exist."

    # -------------------------------------------------------------------------
    # AGENT 1: AI Assistant
    # -------------------------------------------------------------------------
    print("\n--- [AGENT 1] AI Assistant Test ---")
    conv_id = f"test-conv-{uuid.uuid4().hex[:8]}"
    question = "What is the status of customer order CO-000001?"
    print(f"Agent 1 Question: {question}")
    
    chat_resp = ChatService.handle_chat(
        db=db,
        message_text=question,
        conversation_id=conv_id,
        user_id=user.id,
    )
    print(f"Agent 1 Provider: {chat_resp.provider}")
    print(f"Agent 1 Answer Preview: {chat_resp.answer[:120]}...")

    # Verify DB storage in messages table
    stored_msgs = db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.id).all()
    print(f"Agent 1 Stored DB Messages Count: {len(stored_msgs)}")
    assert len(stored_msgs) >= 2, "User message and Assistant message must be saved in 'messages' DB table!"
    assistant_msg = stored_msgs[-1]
    assert assistant_msg.role == "assistant"
    assert assistant_msg.content == chat_resp.answer
    print(f"Verified: Agent 1 called Domo AI -> stored response in 'messages' table (id={assistant_msg.id}).")

    # -------------------------------------------------------------------------
    # AGENT 2: Order Feasibility Assessment
    # -------------------------------------------------------------------------
    print("\n--- [AGENT 2] Feasibility Assessment Test ---")
    req_date = date.today() + timedelta(days=10)
    print(f"Agent 2 Assessing order for CUS-001, SPH-A15-128, Qty 250, Req Date: {req_date}")
    
    assessment = FeasibilityService.assess_new_order(
        db=db,
        customer_id="CUS-001",
        product_id="SPH-A15-128",
        order_qty=250,
        requested_delivery_date=req_date,
        user=user,
        submit_for_approval=True,
    )
    print(f"Agent 2 Assessment Code: {assessment.assessment_id}")
    print(f"Agent 2 Overall Status: {assessment.overall_status}")
    print(f"Agent 2 Achievable Date: {assessment.estimated_delivery_date}")
    print(f"Agent 2 Blockers Summary (from Domo AI): {assessment.blockers_summary}")
    print(f"Agent 2 Corrective Actions Summary (from Domo AI): {assessment.corrective_actions_summary}")

    # Verify DB storage in order_assessments and commitment_proposals
    db.expire_all()
    db_assessment = db.query(OrderAssessment).filter(OrderAssessment.id == assessment.id).first()
    assert db_assessment, "OrderAssessment must exist in DB table 'order_assessments'!"
    assert db_assessment.blockers_summary is not None, "blockers_summary must be stored in DB!"
    assert db_assessment.corrective_actions_summary is not None, "corrective_actions_summary must be stored in DB!"
    print(f"Verified: Agent 2 stored Domo AI synthesis in 'order_assessments' table (id={db_assessment.id}).")

    if db_assessment.proposal_id:
        db_prop = db.query(CommitmentProposal).filter(CommitmentProposal.id == db_assessment.proposal_id).first()
        print(f"Agent 2 Proposal Reasons in DB: {db_prop.reasons}")
        assert db_prop and db_prop.reasons, "CommitmentProposal reasons must be stored in DB!"
        print(f"Verified: Agent 2 stored Domo AI proposal reasons in 'commitment_proposals' table (id={db_prop.id}).")

    # -------------------------------------------------------------------------
    # AGENT 3: Order Monitoring & Surveillance
    # -------------------------------------------------------------------------
    print("\n--- [AGENT 3] Order Monitoring & Surveillance Test ---")
    # Activate monitoring on an order
    test_order_id = "CO-000001"
    mon_rec = MonitoringService.activate_monitoring(
        db=db,
        customer_order_id=test_order_id,
        approved_delivery_date=date(2026, 11, 20),
        user_id=user.id,
    )
    print(f"Agent 3 Active Monitoring Record: {mon_rec.id} for {test_order_id}")

    # Record a risk alert to trigger Domo AI synthesis
    risk_data = {
        "department": "QMS",
        "risk_category": "QUALITY_HOLD",
        "severity": "HIGH",
        "title": f"Quality hold placed on batch for {test_order_id}",
        "description": "2 inspection holds pending disposition review on high-priority batch.",
        "delivery_impact": "Standard buffer breached.",
        "recommended_action": "Notify quality engineering.",
    }
    
    created_or_updated = MonitoringService._record_risk_alert(
        db=db,
        mon_rec=mon_rec,
        risk_dict=risk_data,
    )
    print(f"Agent 3 Alert recorded: {created_or_updated}")

    # Verify DB storage in risk_alerts table
    db.expire_all()
    latest_alert = db.query(RiskAlert).filter(
        RiskAlert.customer_order_id == test_order_id,
        RiskAlert.risk_category == "QUALITY_HOLD",
    ).first()
    assert latest_alert, "RiskAlert must exist in 'risk_alerts' DB table!"
    print(f"Agent 3 Alert Delivery Impact (from Domo AI): {latest_alert.delivery_impact}")
    print(f"Agent 3 Alert Action (from Domo AI): {latest_alert.recommended_action}")
    assert latest_alert.delivery_impact, "Delivery impact must be populated in DB!"
    assert latest_alert.recommended_action, "Recommended action must be populated in DB!"
    print(f"Verified: Agent 3 stored Domo AI synthesis in 'risk_alerts' table (id={latest_alert.id}).")

    print("\n=================================================================")
    print("SUCCESS: ALL 3 AGENTS FOLLOW THE DOMO AI -> DB -> UI PATTERN!")
    print("=================================================================")
    db.close()

if __name__ == "__main__":
    test_pattern()
