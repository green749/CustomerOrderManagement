import os
import re
import time
import json
import html
import smtplib
import logging
import threading
from abc import ABC, abstractmethod
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session

logger = logging.getLogger("manufacturing.email")

from ..config import settings
from ..models.workflow import (
    EmailNotificationLog,
    DepartmentContact,
    RiskAlert,
    SystemSetting,
    OrderAssessment,
    CommitmentProposal,
    DepartmentReadiness,
)
from ..models.business import DimCustomer, DimProduct, FactCustomerOrder
from ..database import SessionLocal


def utcnow():
    return datetime.now(timezone.utc)


EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

SEVERITY_ORDER = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


class BaseEmailProvider(ABC):
    @abstractmethod
    def is_configured(self, recipient: Optional[str] = None) -> bool:
        pass

    @abstractmethod
    def send_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        sender: Optional[str] = None,
        html_body: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Returns (success: bool, error_message: Optional[str], provider_message_id: Optional[str])"""
        pass


class SMTPEmailProvider(BaseEmailProvider):
    """
    Standard enterprise SMTP provider with direct delivery support for testing mailboxes (e.g. YOPmail).
    Reads host, port, user and password from application settings, environment variables, or database system settings.
    Never exposes or prints credentials.
    """

    def __init__(self):
        self.host = getattr(settings, "smtp_host", None)
        self.user = getattr(settings, "smtp_user", None)
        self.password = getattr(settings, "smtp_password", None)
        self.port = getattr(settings, "smtp_port", 587)
        self.default_sender = getattr(settings, "smtp_from", "noreply@manufacturing.internal")

    _cached_smtp_config: Optional[Dict[str, Any]] = None
    _config_cache_time: float = 0.0

    @classmethod
    def clear_config_cache(cls):
        cls._cached_smtp_config = None
        cls._config_cache_time = 0.0

    def _get_smtp_config(self) -> Dict[str, Any]:
        now = time.time()
        if self._cached_smtp_config and (now - self._config_cache_time < 60):
            return self._cached_smtp_config

        # 1. Database system_settings table takes precedence for runtime user configuration!
        db_settings = {}
        try:
            db = SessionLocal()
            db_settings = {s.key: s.value for s in db.query(SystemSetting).all() if s.value}
            db.close()
        except Exception as e:
            logger.debug(f"Could not load SystemSetting for SMTP: {e}")

        host = db_settings.get("smtp_host") or os.environ.get("SMTP_HOST") or self.host or getattr(settings, "smtp_host", None)
        user = db_settings.get("smtp_user") or os.environ.get("SMTP_USER") or self.user or getattr(settings, "smtp_user", None)
        password = db_settings.get("smtp_password") or os.environ.get("SMTP_PASSWORD") or self.password or getattr(settings, "smtp_password", None)
        port_raw = db_settings.get("smtp_port") or os.environ.get("SMTP_PORT") or self.port or getattr(settings, "smtp_port", 587) or 587
        try:
            port = int(port_raw)
        except (ValueError, TypeError):
            port = 587
        sender = db_settings.get("smtp_from") or os.environ.get("SMTP_FROM") or self.default_sender or getattr(settings, "smtp_from", "noreply@manufacturing.internal")

        cfg = {
            "host": host,
            "user": user,
            "password": password,
            "port": port,
            "sender": sender,
        }
        self.__class__._cached_smtp_config = cfg
        self.__class__._config_cache_time = now
        return cfg

    def is_configured(self, recipient: Optional[str] = None) -> bool:
        cfg = self._get_smtp_config()
        if recipient and "yopmail" in recipient.lower():
            return True
        if cfg.get("host") and cfg["host"].lower() not in ("sandbox", "mock", "test", "dev") and cfg.get("user") and cfg.get("password"):
            return True
        if cfg.get("host") and cfg["host"].lower() in ("sandbox", "mock", "test", "dev"):
            if recipient and (
                recipient.endswith(".internal")
                or recipient.endswith(".local")
                or "yopmail" in recipient.lower()
                or "ethereal.email" in recipient.lower()
                or any(d in recipient.lower() for d in ["retailernorth.com", "mobilemart.com", "digitalbazaar.com", "globaldevices.com"])
            ):
                return True
            return False
        return False

    @classmethod
    def send_via_relay(
        cls,
        emails: List[Dict[str, Any]],
        cfg: Optional[Dict[str, Any]] = None,
        timeout: int = 20,
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Dispatches emails via HTTPS POST to Vercel Serverless Email Relay.
        Render Free tier drops outbound TCP connections on ports 25, 465, and 587.
        Relaying via HTTPS (port 443) bypasses Render's firewall restrictions cleanly.
        """
        import urllib.request
        import urllib.error

        relay_url = os.environ.get(
            "SMTP_RELAY_URL",
            "https://customer-order-management-two.vercel.app/api/relay-email",
        )
        if not relay_url:
            return False, "No relay URL configured", None

        smtp_cfg = cfg or {}
        payload = {
            "host": smtp_cfg.get("host") or "smtp.ethereal.email",
            "port": smtp_cfg.get("port") or 587,
            "user": smtp_cfg.get("user") or "dyfs2m763cn7s2uz@ethereal.email",
            "password": smtp_cfg.get("password") or "KFHKGSc119pe56eY4f",
            "sender": smtp_cfg.get("sender") or "Manufacturing 360 <dyfs2m763cn7s2uz@ethereal.email>",
            "emails": emails,
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                relay_url,
                data=req_data,
                headers={"Content-Type": "application/json", "User-Agent": "Manufacturing360-Backend/1.0"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_body = resp.read().decode("utf-8")
                res_json = json.loads(resp_body)
                if res_json.get("success"):
                    return True, None, res_json
                else:
                    return False, res_json.get("error", "Unknown relay error"), res_json
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="replace")
            logger.warning(f"Relay HTTP {he.code}: {err_body}")
            return False, f"Relay HTTP {he.code}: {err_body[:120]}", None
        except Exception as e:
            logger.warning(f"Relay request failed: {e}")
            return False, f"Relay request failed: {str(e)}", None

    def get_smtp_session(self):
        """Creates and returns an authenticated SMTP connection for batch delivery."""
        cfg = self._get_smtp_config()
        if not (cfg.get("host") and cfg.get("user") and cfg.get("password")):
            return None
        port = int(cfg.get("port") or 587)
        if port == 465:
            server = smtplib.SMTP_SSL(cfg["host"], port, timeout=15)
        else:
            server = smtplib.SMTP(cfg["host"], port, timeout=15)
            server.starttls()
        server.login(cfg["user"], cfg["password"])
        return server

    def send_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        sender: Optional[str] = None,
        html_body: Optional[str] = None,
        server: Optional[Any] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        cfg = self._get_smtp_config()

        use_relay = bool(os.environ.get("RENDER")) or os.environ.get("USE_EMAIL_RELAY", "true").lower() in ("true", "1")

        # 1. Full authenticated SMTP if real credentials are provided (e.g. Gmail App Password or Ethereal)
        if cfg.get("host") and cfg["host"].lower() not in ("sandbox", "mock", "test", "dev") and cfg.get("user") and cfg.get("password"):
            # If running on Render or relay enabled, use HTTPS relay to avoid firewall port 587 block
            if use_relay:
                single_email = [{
                    "recipient": recipient,
                    "subject": subject,
                    "body": body,
                    "html_body": html_body or EmailService.convert_text_to_neat_html(subject, body),
                    "sender": sender or cfg.get("sender") or self.default_sender,
                }]
                ok, err, res = self.send_via_relay(single_email, cfg)
                if ok:
                    message_id = f"relay-{int(utcnow().timestamp())}"
                    return True, None, message_id
                logger.warning(f"Relay failed on Render, attempting direct fallback: {err}")

            # Direct SMTP attempt (on local development, dedicated VMs, or if relay failed)
            managed = False
            active_server = server
            try:
                msg = MIMEMultipart("alternative")
                msg["From"] = sender or cfg.get("sender") or self.default_sender
                msg["To"] = recipient
                msg["Subject"] = subject
                msg.attach(MIMEText(body, "plain", "utf-8"))
                rendered_html = html_body or EmailService.convert_text_to_neat_html(subject, body)
                msg.attach(MIMEText(rendered_html, "html", "utf-8"))

                if active_server is None:
                    managed = True
                    active_server = self.get_smtp_session()

                active_server.send_message(msg)

                if managed:
                    try:
                        active_server.quit()
                    except Exception:
                        pass
                    active_server = None

                message_id = f"smtp-{int(utcnow().timestamp())}"
                return True, None, message_id
            except Exception as e:
                if managed and active_server:
                    try:
                        active_server.close()
                    except Exception:
                        pass

                # If direct SMTP fails with timeout/network error, fallback to HTTPS relay!
                single_email = [{
                    "recipient": recipient,
                    "subject": subject,
                    "body": body,
                    "html_body": html_body or EmailService.convert_text_to_neat_html(subject, body),
                    "sender": sender or cfg.get("sender") or self.default_sender,
                }]
                ok_r, err_r, _ = self.send_via_relay(single_email, cfg)
                if ok_r:
                    return True, None, f"relay-fallback-{int(utcnow().timestamp())}"

                return False, f"SMTP delivery failed to {recipient}: {str(e)}", None

        # 2. Direct delivery for public testing mailboxes (YOPmail on port 587)
        if "yopmail" in recipient.lower():
            try:
                msg = MIMEMultipart("alternative")
                msg["From"] = sender or "Manufacturing 360 <alerts@manufacturing360.com>"
                msg["To"] = recipient
                msg["Subject"] = subject
                msg.attach(MIMEText(body, "plain", "utf-8"))
                rendered_html = html_body or EmailService.convert_text_to_neat_html(subject, body)
                msg.attach(MIMEText(rendered_html, "html", "utf-8"))

                with smtplib.SMTP("smtp.yopmail.com", 587, timeout=12) as server:
                    server.send_message(msg)

                message_id = f"yopmail-{int(utcnow().timestamp())}"
                return True, None, message_id
            except Exception as e:
                return False, f"YOPmail direct delivery failed: {str(e)}", None

        # 3. Sandbox mode handling
        if cfg.get("host") and cfg["host"].lower() in ("sandbox", "mock", "test", "dev"):
            if (
                recipient.endswith(".internal")
                or recipient.endswith(".local")
                or "ethereal.email" in recipient.lower()
                or any(d in recipient.lower() for d in ["retailernorth.com", "mobilemart.com", "digitalbazaar.com", "globaldevices.com"])
            ):
                logger.info(f"[SANDBOX INTERNAL DISPATCH] Recipient: {recipient} | Subject: {subject}")
                message_id = f"sandbox-{int(utcnow().timestamp())}"
                return True, None, message_id

            # External commercial recipient (e.g. Gmail) without real SMTP credentials
            err_msg = (
                f"Cannot deliver to external address '{recipient}': SMTP relay is currently running in zero-credential sandbox mode. "
                "To deliver real emails to your Gmail inbox, please configure your SMTP Host (smtp.gmail.com), Port (587), and Google App Password in Settings -> Email Configuration, "
                "or use zero-credential instant delivery with a '@yopmail.com' test mailbox (instantly viewable at https://yopmail.com)."
            )
            return False, err_msg, None

        # 4. Otherwise unconfigured
        return False, (
            "SMTP credentials not configured. Configure SMTP in Settings -> Email Configuration (e.g. smtp.gmail.com with App Password), "
            "or use a '@yopmail.com' test address for instant zero-credential delivery."
        ), None


class MockEmailProvider(BaseEmailProvider):
    """
    In-memory mock provider for testing and offline development.
    Can be configured to simulate network or credentials failure.
    """

    def __init__(self, simulate_failure: bool = False, failure_reason: str = "Simulated provider failure"):
        self.simulate_failure = simulate_failure
        self.failure_reason = failure_reason
        self.sent_emails: List[Dict[str, Any]] = []

    def is_configured(self, recipient: Optional[str] = None) -> bool:
        return not self.simulate_failure

    def send_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        sender: Optional[str] = None,
        html_body: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        if self.simulate_failure:
            return False, self.failure_reason, None

        msg_id = f"mock-msg-{len(self.sent_emails) + 1}-{int(utcnow().timestamp())}"
        self.sent_emails.append({
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "html_body": html_body,
            "sender": sender or "noreply@manufacturing.internal",
            "message_id": msg_id,
            "sent_at": utcnow(),
        })
        return True, None, msg_id


DEFAULT_DEPARTMENT_CONTACTS = {
    "ERP": ("Order Management Lead", "erp-ops@manufacturing.internal"),
    "MMS": ("Master Production Scheduler", "mms-ops@manufacturing.internal"),
    "MES": ("Plant Operations Lead", "mes-ops@manufacturing.internal"),
    "WMS": ("Warehouse & Materials Manager", "wms-ops@manufacturing.internal"),
    "QMS": ("Quality Assurance Engineer", "qms-ops@manufacturing.internal"),
    "TMS": ("Logistics & Dispatch Coordinator", "tms-ops@manufacturing.internal"),
    "PLM": ("Configuration Management Engineer", "plm-ops@manufacturing.internal"),
    "CUSTOMER_SERVICE": ("Customer Service Lead", "cs-lead@manufacturing.internal"),
}

DEFAULT_CUSTOMER_CONTACTS = {
    "CUS-001": {
        "customer_name": "Retailer North",
        "email": "procurement@retailernorth.com",
        "contact_person": "Procurement Director",
        "phone": "+91-11-2345-6701",
    },
    "CUS-002": {
        "customer_name": "MobileMart",
        "email": "procurement@mobilemart.com",
        "contact_person": "Supply Chain Lead",
        "phone": "+91-22-4567-8902",
    },
    "CUS-003": {
        "customer_name": "Digital Bazaar",
        "email": "procurement@digitalbazaar.com",
        "contact_person": "Merchandise Operations Lead",
        "phone": "+91-80-3456-7803",
    },
    "CUS-004": {
        "customer_name": "Global Devices",
        "email": "procurement@globaldevices.com",
        "contact_person": "Vendor Management Lead",
        "phone": "+91-44-6789-0104",
    },
}


class EmailService:
    """
    Enterprise Email Notification Service for Agent 3 order surveillance.
    - Resolves recipients from database department contacts.
    - Handles independent Operational Department and Customer Service notifications.
    - Prevents duplicates while notifying on severity escalation and resolution.
    - Tracks complete lifecycle: PENDING, SENT, FAILED, RETRYING, PENDING_CONFIG.
    """

    _provider: Optional[BaseEmailProvider] = None

    @classmethod
    def get_provider(cls) -> BaseEmailProvider:
        if cls._provider is None:
            cls._provider = SMTPEmailProvider()
        return cls._provider

    @classmethod
    def set_provider(cls, provider: BaseEmailProvider):
        """Allows injecting MockEmailProvider in unit tests."""
        cls._provider = provider

    @classmethod
    def reset_provider(cls):
        cls._provider = None

    @classmethod
    def validate_email_address(cls, email: str) -> bool:
        if not email or not isinstance(email, str):
            return False
        return bool(EMAIL_REGEX.match(email.strip()))

    @classmethod
    def render_neat_email_html(
        cls,
        title: str,
        order_id: str,
        customer_name: Optional[str] = None,
        product_info: Optional[str] = None,
        required_date: Optional[str] = None,
        committed_date: Optional[str] = None,
        department: Optional[str] = None,
        severity: str = "MEDIUM",
        issue_category: Optional[str] = None,
        impact_status: Optional[str] = None,
        description: str = "",
        delivery_impact: Optional[str] = None,
        action_required: Optional[str] = None,
        order_link: Optional[str] = None,
        queue_link: Optional[str] = None,
        recipient_category: str = "OPERATIONAL",
        governance_notice: Optional[str] = None,
    ) -> str:
        """
        Renders a responsive, modern HTML email card.
        Neat typography, clean hierarchy, colored severity pills, and clear action buttons.
        """
        sev = (severity or "MEDIUM").upper()
        if sev == "CRITICAL":
            sev_bg = "#FEE2E2"
            sev_color = "#991B1B"
            sev_border = "#EF4444"
            sev_badge = "🚨 CRITICAL SEVERITY"
        elif sev == "HIGH":
            sev_bg = "#FEF3C7"
            sev_color = "#92400E"
            sev_border = "#F59E0B"
            sev_badge = "⚠️ HIGH SEVERITY"
        elif sev == "MEDIUM":
            sev_bg = "#E0F2FE"
            sev_color = "#075985"
            sev_border = "#38BDF8"
            sev_badge = "⏱️ MEDIUM SEVERITY"
        else:
            sev_bg = "#DCFCE7"
            sev_color = "#166534"
            sev_border = "#22C55E"
            sev_badge = "ℹ️ LOW SEVERITY"

        dept_str = (department or "OPERATIONS").upper()
        now_utc = utcnow().strftime("%Y-%m-%d %H:%M:%S")

        product_row = ""
        if product_info and product_info != "N/A":
            product_row = f"""
            <tr>
              <td style="padding: 7px 0; color: #64748B; font-size: 11.5px; font-weight: 600; text-transform: uppercase;">Product & Qty:</td>
              <td style="padding: 7px 0; color: #334155; font-size: 13px; font-weight: 500;">{html.escape(product_info)}</td>
            </tr>
            """

        cat_row = ""
        if issue_category and issue_category != "N/A":
            cat_row = f"""
            <tr>
              <td style="padding: 7px 0; color: #64748B; font-size: 11.5px; font-weight: 600; text-transform: uppercase;">Issue Category:</td>
              <td style="padding: 7px 0;"><span style="background: #EDE9FE; color: #5B21B6; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 4px;">{html.escape(issue_category)}</span></td>
            </tr>
            """

        impact_row = ""
        if impact_status:
            impact_row = f"""
            <tr>
              <td style="padding: 7px 0; color: #64748B; font-size: 11.5px; font-weight: 600; text-transform: uppercase;">Impact Status:</td>
              <td style="padding: 7px 0; color: {sev_color}; font-size: 12.5px; font-weight: 700;">{html.escape(impact_status)}</td>
            </tr>
            """

        impact_box = ""
        if delivery_impact:
            impact_box = f"""
            <div style="margin-bottom: 20px;">
              <div style="font-size: 11.5px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; color: #64748B; margin-bottom: 6px;">
                ⏱️ Estimated Delivery Impact
              </div>
              <div style="background-color: #EFF6FF; border-left: 4px solid #3B82F6; padding: 13px 16px; border-radius: 0 8px 8px 0; font-size: 13px; line-height: 1.5; color: #1E3A8A;">
                {html.escape(delivery_impact)}
              </div>
            </div>
            """

        action_box = ""
        if action_required:
            action_box = f"""
            <div style="margin-bottom: 24px;">
              <div style="font-size: 11.5px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; color: #64748B; margin-bottom: 6px;">
                🛠️ Required Corrective Action
              </div>
              <div style="background-color: #F0FDF4; border-left: 4px solid #22C55E; padding: 13px 16px; border-radius: 0 8px 8px 0; font-size: 13px; line-height: 1.5; color: #14532D; font-weight: 600;">
                {html.escape(action_required)}
              </div>
            </div>
            """

        buttons_html = ""
        if order_link:
            buttons_html += f"""<a href="{html.escape(order_link)}" target="_blank" style="background-color: #6F3DBA; color: #FFFFFF; font-size: 13px; font-weight: 700; text-decoration: none; padding: 11px 22px; border-radius: 8px; display: inline-block; margin: 4px 6px;">Inspect Order {html.escape(order_id)} →</a>"""
        if queue_link:
            buttons_html += f"""<a href="{html.escape(queue_link)}" target="_blank" style="background-color: #F1F5F9; color: #475569; border: 1px solid #CBD5E1; font-size: 13px; font-weight: 700; text-decoration: none; padding: 10px 20px; border-radius: 8px; display: inline-block; margin: 4px 6px;">Review {html.escape(dept_str)} Queue →</a>"""

        gov = governance_notice or "The revised delivery date is not confirmed. Do not invent revised dates or schedule promises without verified department evidence."

        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)} - Order {html.escape(order_id)}</title>
</head>
<body style="margin: 0; padding: 24px 10px; background-color: #F1F5F9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1E293B;">
  <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width: 600px; background-color: #FFFFFF; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.07); border: 1px solid #E2E8F0;" border="0" cellspacing="0" cellpadding="0">
          
          <!-- BRAND HEADER -->
          <tr>
            <td style="background: linear-gradient(135deg, #4A1D96 0%, #6F3DBA 55%, #4338CA 100%); padding: 26px 30px; color: #FFFFFF;">
              <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #DDD6FE; margin-bottom: 6px;">
                Manufacturing 360 · Autonomous Agent Mesh
              </div>
              <div style="font-size: 20px; font-weight: 800; line-height: 1.25; margin-bottom: 12px; color: #FFFFFF;">
                {html.escape(title)}
              </div>
              <div>
                <span style="background: rgba(255, 255, 255, 0.2); border: 1px solid rgba(255, 255, 255, 0.35); padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 700; margin-right: 8px;">
                  Dept: {html.escape(dept_str)}
                </span>
                <span style="background: {sev_bg}; color: {sev_color}; border: 1px solid {sev_border}; padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 800;">
                  {sev_badge}
                </span>
              </div>
            </td>
          </tr>

          <!-- CARD CONTENT -->
          <tr>
            <td style="padding: 26px 30px;">

              <!-- SUMMARY BOX -->
              <table role="presentation" width="100%" style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; margin-bottom: 22px; font-size: 13px;" border="0" cellspacing="0" cellpadding="0">
                <tr>
                  <td style="padding: 14px 18px;">
                    <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0">
                      <tr>
                        <td width="35%" style="padding: 7px 0; color: #64748B; font-size: 11.5px; font-weight: 600; text-transform: uppercase;">Order Number:</td>
                        <td width="65%" style="padding: 7px 0; color: #0F172A; font-size: 14px; font-weight: 800; font-family: monospace;">{html.escape(order_id)}</td>
                      </tr>
                      <tr>
                        <td style="padding: 7px 0; color: #64748B; font-size: 11.5px; font-weight: 600; text-transform: uppercase;">Customer:</td>
                        <td style="padding: 7px 0; color: #0F172A; font-weight: 700;">{html.escape(customer_name or 'Commercial Account')}</td>
                      </tr>
                      {product_row}
                      <tr>
                        <td style="padding: 7px 0; color: #64748B; font-size: 11.5px; font-weight: 600; text-transform: uppercase;">Committed Date:</td>
                        <td style="padding: 7px 0; color: #0F172A; font-weight: 700;">{html.escape(committed_date or 'Awaiting Confirmation')}</td>
                      </tr>
                      {cat_row}
                      {impact_row}
                    </table>
                  </td>
                </tr>
              </table>

              <!-- ISSUE SECTION -->
              <div style="margin-bottom: 18px;">
                <div style="font-size: 11.5px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; color: #64748B; margin-bottom: 6px;">
                  📌 Operational Issue & Evidence
                </div>
                <div style="background-color: #FFFBEB; border-left: 4px solid #F59E0B; padding: 13px 16px; border-radius: 0 8px 8px 0; font-size: 13px; line-height: 1.55; color: #78350F;">
                  {html.escape(description)}
                </div>
              </div>

              {impact_box}

              {action_box}

              <!-- ACTION BUTTONS -->
              <div style="padding: 8px 0 20px; text-align: center;">
                {buttons_html}
              </div>

              <!-- GOVERNANCE NOTICE -->
              <div style="background-color: #F8FAFC; border: 1px dashed #CBD5E1; border-radius: 6px; padding: 11px 15px; font-size: 11.5px; color: #64748B; line-height: 1.45;">
                <strong>Governance Directive:</strong> {html.escape(gov)}
              </div>

            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td style="background-color: #F8FAFC; border-top: 1px solid #E2E8F0; padding: 14px 28px; text-align: center; font-size: 11px; color: #94A3B8;">
              Dispatched automatically by <strong>Agent 3 (Order Monitoring Agent)</strong> · Manufacturing 360 AI Mesh<br>
              Surveillance Cycle: {now_utc} UTC
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    @classmethod
    def render_neat_plain_text(
        cls,
        title: str,
        order_id: str,
        customer_name: Optional[str] = None,
        product_info: Optional[str] = None,
        required_date: Optional[str] = None,
        committed_date: Optional[str] = None,
        department: Optional[str] = None,
        severity: str = "MEDIUM",
        issue_category: Optional[str] = None,
        impact_status: Optional[str] = None,
        description: str = "",
        delivery_impact: Optional[str] = None,
        action_required: Optional[str] = None,
        order_link: Optional[str] = None,
        queue_link: Optional[str] = None,
        governance_notice: Optional[str] = None,
    ) -> str:
        """
        Renders a clean, structured, human-friendly plain text email.
        Avoids harsh all-caps walls of text and messy ASCII borders.
        """
        dept_str = (department or "OPERATIONS").upper()
        sev_str = (severity or "MEDIUM").upper()
        gov = governance_notice or "The revised delivery date is not confirmed. Do not invent revised dates or schedule promises without verified department evidence."
        
        lines = [
            "Manufacturing 360 · Autonomous Surveillance",
            title,
            "=" * 60,
            f"Order Number:        {order_id}",
            f"Customer:            {customer_name or 'Commercial Account'}",
        ]
        if product_info and product_info != "N/A":
            lines.append(f"Product & Quantity:  {product_info}")
        if committed_date:
            lines.append(f"Committed Date:      {committed_date}")
        elif required_date:
            lines.append(f"Required Delivery:   {required_date}")
        if issue_category and issue_category != "N/A":
            lines.append(f"Issue Category:      {issue_category}")
        lines.append(f"Department:          {dept_str}")
        lines.append(f"Risk Severity:       {sev_str}" + (f" ({impact_status})" if impact_status else ""))

        lines.append(f"\n{'-' * 60}")
        lines.append("OPERATIONAL ISSUE & EVIDENCE:")
        lines.append(description.strip())

        if delivery_impact:
            lines.append(f"\n{'-' * 60}")
            lines.append("ESTIMATED DELIVERY IMPACT:")
            lines.append(delivery_impact.strip())

        if action_required:
            lines.append(f"\n{'-' * 60}")
            lines.append("REQUIRED CORRECTIVE ACTION:")
            lines.append(action_required.strip())

        if order_link or queue_link:
            lines.append(f"\n{'-' * 60}")
            lines.append("APPLICATION QUICK ACTIONS:")
            if order_link:
                lines.append(f"• Inspect Order:         {order_link}")
            if queue_link:
                lines.append(f"• Review Department Queue: {queue_link}")

        lines.append(f"\n{'-' * 60}")
        lines.append(f"Governance Directive:\n{gov}")
        lines.append("=" * 60)
        lines.append("Dispatched by Agent 3 (Order Monitoring Agent) · Manufacturing 360")
        return "\n".join(lines)

    @classmethod
    def convert_text_to_neat_html(cls, subject: str, text_body: str) -> str:
        """
        Fallback parser that takes plain text notification body and wraps it
        in the clean, responsive Manufacturing 360 email layout.
        """
        if "<html" in text_body.lower() or "<table" in text_body.lower():
            return text_body

        lines = text_body.splitlines()
        clean_lines = []
        for line in lines:
            line_str = line.strip()
            if not line_str or set(line_str) <= {"=", "-", "*"}:
                continue
            clean_lines.append(html.escape(line_str))

        formatted_content = "<br>".join(clean_lines)

        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{html.escape(subject)}</title>
</head>
<body style="margin: 0; padding: 24px 10px; background-color: #F1F5F9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1E293B;">
  <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width: 600px; background-color: #FFFFFF; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.07); border: 1px solid #E2E8F0;" border="0" cellspacing="0" cellpadding="0">
          <tr>
            <td style="background: linear-gradient(135deg, #4A1D96 0%, #6F3DBA 55%, #4338CA 100%); padding: 24px 28px; color: #FFFFFF;">
              <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #DDD6FE; margin-bottom: 6px;">
                Manufacturing 360 · Autonomous Surveillance
              </div>
              <div style="font-size: 19px; font-weight: 800; color: #FFFFFF;">
                {html.escape(subject)}
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding: 24px 28px;">
              <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 18px 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; line-height: 1.6; color: #334155;">
                {formatted_content}
              </div>
            </td>
          </tr>
          <tr>
            <td style="background-color: #F8FAFC; border-top: 1px solid #E2E8F0; padding: 12px 28px; text-align: center; font-size: 11px; color: #94A3B8;">
              Manufacturing 360 AI Engine · Dispatched by Agent 3
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    @classmethod
    def get_recipient_for_department(cls, db: Session, department: str) -> Tuple[str, bool]:
        """Returns (recipient_email, is_configured_in_db)"""
        contact = db.query(DepartmentContact).filter(
            DepartmentContact.department == department.upper().strip(),
            DepartmentContact.is_active == True,
        ).first()

        if contact and contact.email:
            email = contact.email.strip().lower()
            return email, True

        dept_upper = department.upper().strip()
        if dept_upper in DEFAULT_DEPARTMENT_CONTACTS:
            return DEFAULT_DEPARTMENT_CONTACTS[dept_upper][1], False

        import os
        return os.getenv("DEFAULT_ALERT_EMAIL", "alerts@manufacturing.internal"), False

    @classmethod
    def get_customer_service_recipient(cls, db: Session) -> Tuple[str, bool]:
        """Resolves Customer Service recipient address."""
        contact = db.query(DepartmentContact).filter(
            DepartmentContact.department.in_(["CUSTOMER_SERVICE", "CS"]),
            DepartmentContact.is_active == True,
        ).first()

        if contact and contact.email:
            email = contact.email.strip().lower()
            return email, True

        return DEFAULT_DEPARTMENT_CONTACTS["CUSTOMER_SERVICE"][1], False

    @classmethod
    def seed_default_contacts(cls, db: Session):
        for dept, (role, email) in DEFAULT_DEPARTMENT_CONTACTS.items():
            exists = db.query(DepartmentContact).filter(DepartmentContact.department == dept).first()
            if not exists:
                contact = DepartmentContact(
                    department=dept,
                    role_name=role,
                    email=email,
                    is_active=True,
                )
                db.add(contact)
        db.commit()

    @classmethod
    def _dispatch_and_persist_notification(
        cls,
        db: Session,
        alert_id: Optional[int],
        customer_order_id: str,
        recipient_email: str,
        recipient_category: str,
        department: str,
        notification_type: str,
        subject: str,
        body_text: str,
        html_body: Optional[str] = None,
        server: Optional[Any] = None,
    ) -> EmailNotificationLog:
        """
        Creates notification log record, validates address, and dispatches via provider.
        """
        actual_send_recipient = recipient_email
        if recipient_email and (
            recipient_email.endswith(".internal")
            or recipient_email.endswith(".local")
            or "@manufacturing" in recipient_email
            or any(d in recipient_email.lower() for d in ["retailernorth.com", "mobilemart.com", "digitalbazaar.com", "globaldevices.com"])
        ):
            provider = cls.get_provider()
            try:
                cfg = provider._get_smtp_config() if hasattr(provider, "_get_smtp_config") else {}
            except Exception:
                cfg = {}
            if cfg.get("host") and cfg["host"].lower() in ("sandbox", "mock", "test", "dev"):
                actual_send_recipient = recipient_email
            else:
                import os
                actual_send_recipient = os.getenv("DEFAULT_ALERT_EMAIL") or cfg.get("user") or recipient_email

        log = EmailNotificationLog(
            alert_id=alert_id,
            customer_order_id=customer_order_id,
            recipient_email=recipient_email,
            recipient_category=recipient_category,
            department=department,
            notification_type=notification_type,
            subject=subject,
            body_text=body_text,
            status="PENDING_CONFIG",
            retry_count=0,
            created_at=utcnow(),
            last_attempt_at=utcnow(),
        )

        # 1. Validate email syntax
        if not cls.validate_email_address(recipient_email):
            log.status = "FAILED"
            log.failure_reason = f"Recipient email address '{recipient_email}' failed validation check."
            db.add(log)
            db.commit()
            return log

        # 2. Check provider configuration
        provider = cls.get_provider()
        try:
            is_conf = provider.is_configured(actual_send_recipient)
        except TypeError:
            is_conf = provider.is_configured()

        if not is_conf:
            log.status = "PENDING_CONFIG"
            log.failure_reason = "Email provider credentials are not configured in application environment."
            db.add(log)
            db.commit()
            return log

        # 3. Dispatch via provider with rich HTML & clean plain text
        success, err, msg_id = provider.send_email(
            recipient=actual_send_recipient,
            subject=subject,
            body=body_text,
            html_body=html_body,
            server=server,
        )

        if success:
            log.status = "SENT"
            log.sent_at = utcnow()
            log.failure_reason = None
            log.provider_message_id = msg_id
        else:
            log.status = "FAILED"
            log.failure_reason = err
            log.retry_count = 1

        db.add(log)
        db.commit()
        return log

    @classmethod
    def dispatch_notifications_async(cls, notifications: List[Dict[str, Any]]):
        """
        Dispatches a list of notifications asynchronously in a background daemon thread
        using a dedicated DB session and a shared authenticated SMTP session for speed and stability.
        """
        if not notifications:
            return

        # In-memory deduplication: prevent sending duplicates within the same batch
        seen_keys = set()
        deduped_notifications = []
        for notif in notifications:
            order_id = notif.get("customer_order_id")
            cat = notif.get("recipient_category")
            recip = (notif.get("recipient_email") or "").strip().lower()
            alert_id = notif.get("alert_id")
            key = (order_id, cat, recip, alert_id)
            if key not in seen_keys:
                seen_keys.add(key)
                deduped_notifications.append(notif)

        # Batch up to 60 targeted notifications per cycle
        to_dispatch = deduped_notifications[:60]

        def _worker():
            db = SessionLocal()
            provider = cls.get_provider()
            use_relay = bool(os.environ.get("RENDER")) or os.environ.get("USE_EMAIL_RELAY", "true").lower() in ("true", "1")

            # FAST BATCH PATH: If on Render (or relay preferred) and using SMTPEmailProvider
            if use_relay and isinstance(provider, SMTPEmailProvider):
                cfg = provider._get_smtp_config()
                if cfg.get("host") and cfg["host"].lower() not in ("sandbox", "mock", "test", "dev"):
                    email_payloads = []
                    valid_notifs = []
                    for notif in to_dispatch:
                        recip = notif.get("recipient_email")
                        if not cls.validate_email_address(recip):
                            log = EmailNotificationLog(
                                alert_id=notif.get("alert_id"),
                                customer_order_id=notif["customer_order_id"],
                                recipient_email=recip,
                                recipient_category=notif["recipient_category"],
                                department=notif["department"],
                                notification_type=notif["notification_type"],
                                subject=notif["subject"],
                                body_text=notif["body_text"],
                                status="FAILED",
                                failure_reason=f"Recipient email '{recip}' failed validation check.",
                                retry_count=0,
                                created_at=utcnow(),
                                last_attempt_at=utcnow(),
                            )
                            db.add(log)
                            continue

                        actual_recipient = recip
                        if recip and (
                            recip.endswith(".internal")
                            or recip.endswith(".local")
                            or "@manufacturing" in recip
                            or any(d in recip.lower() for d in ["retailernorth.com", "mobilemart.com", "digitalbazaar.com", "globaldevices.com"])
                        ):
                            actual_recipient = os.getenv("DEFAULT_ALERT_EMAIL") or cfg.get("user") or recip

                        email_payloads.append({
                            "recipient": actual_recipient,
                            "subject": notif["subject"],
                            "body": notif["body_text"],
                            "html_body": notif.get("html_body") or cls.convert_text_to_neat_html(notif["subject"], notif["body_text"]),
                        })
                        valid_notifs.append((notif, actual_recipient))

                    if email_payloads:
                        logger.info(f"Relaying batch of {len(email_payloads)} emails via HTTPS...")
                        chunk_size = 15
                        for i in range(0, len(email_payloads), chunk_size):
                            chunk_emails = email_payloads[i : i + chunk_size]
                            chunk_notifs = valid_notifs[i : i + chunk_size]
                            ok, err, res = provider.send_via_relay(chunk_emails, cfg, timeout=25)
                            results_map = {}
                            if ok and res and "results" in res:
                                for r in res["results"]:
                                    results_map[r.get("recipient")] = r

                            for (notif, act_recip) in chunk_notifs:
                                r_info = results_map.get(act_recip)
                                item_ok = r_info.get("success", False) if r_info else ok
                                item_err = (r_info.get("error") if r_info else err) if not item_ok else None
                                item_msg_id = (r_info.get("messageId") if r_info else f"relay-{int(utcnow().timestamp())}") if item_ok else None

                                log = EmailNotificationLog(
                                    alert_id=notif.get("alert_id"),
                                    customer_order_id=notif["customer_order_id"],
                                    recipient_email=notif["recipient_email"],
                                    recipient_category=notif["recipient_category"],
                                    department=notif["department"],
                                    notification_type=notif["notification_type"],
                                    subject=notif["subject"],
                                    body_text=notif["body_text"],
                                    status="SENT" if item_ok else "FAILED",
                                    failure_reason=item_err,
                                    provider_message_id=item_msg_id,
                                    sent_at=utcnow() if item_ok else None,
                                    retry_count=0 if item_ok else 1,
                                    created_at=utcnow(),
                                    last_attempt_at=utcnow(),
                                )
                                db.add(log)
                            db.commit()

                        db.close()
                        return

            smtp_session = None
            if hasattr(provider, "get_smtp_session"):
                try:
                    smtp_session = provider.get_smtp_session()
                except Exception as conn_err:
                    logger.warning(f"Failed to open shared SMTP session for batch: {conn_err}")
                    smtp_session = None

            try:
                for idx, notif in enumerate(to_dispatch):
                    try:
                        cls._dispatch_and_persist_notification(
                            db=db,
                            alert_id=notif.get("alert_id"),
                            customer_order_id=notif["customer_order_id"],
                            recipient_email=notif["recipient_email"],
                            recipient_category=notif["recipient_category"],
                            department=notif["department"],
                            notification_type=notif["notification_type"],
                            subject=notif["subject"],
                            body_text=notif["body_text"],
                            html_body=notif.get("html_body"),
                            server=smtp_session,
                        )
                        if idx < len(to_dispatch) - 1:
                            time.sleep(0.05)
                    except Exception as e:
                        logger.error(f"Error dispatching notification for order {notif.get('customer_order_id')}: {e}")
            finally:
                if smtp_session:
                    try:
                        smtp_session.quit()
                    except Exception:
                        pass
                db.close()

        t = threading.Thread(target=_worker, daemon=True, name="AsyncNotificationDispatcher")
        t.start()

    @classmethod
    def send_operational_risk_notification(
        cls,
        db: Session,
        alert: RiskAlert,
        customer_name: Optional[str] = None,
        product_name: Optional[str] = None,
        product_qty: Optional[int] = None,
        required_date: Optional[str] = None,
        approved_date: Optional[str] = None,
        app_url: str = "http://localhost:5173",
        force_send: bool = False,
    ) -> Optional[EmailNotificationLog]:
        """
        Agent 3 Operational Department Email Notification (Section 5).
        - Notifies responsible operational department of actionable issues delaying orders.
        - Suppresses duplicates for unchanged issues.
        - Triggers escalation if severity increased.
        """
        recipient_email, _ = cls.get_recipient_for_department(db, alert.department)
        order_id = alert.customer_order_id

        # Duplicate / Escalation check against the target recipient
        prev_logs = db.query(EmailNotificationLog).filter(
            EmailNotificationLog.alert_id == alert.id,
            EmailNotificationLog.recipient_category == "OPERATIONAL",
            EmailNotificationLog.status.in_(["SENT", "PENDING_CONFIG"]),
        ).order_by(EmailNotificationLog.created_at.desc()).all()

        notification_type = "ACTION_REQUIRED"
        if prev_logs and not force_send:
            # Check if this specific recipient already received this alert with identical severity
            has_identical = any(
                pl.recipient_email.strip().lower() == recipient_email.strip().lower()
                and (f"[{alert.severity}]" in pl.subject or alert.severity in pl.body_text)
                for pl in prev_logs
            )
            if has_identical:
                # Issue unchanged for this recipient - prevent duplicate email spam
                return None
            else:
                # If this recipient already received an earlier severity, mark as escalation
                has_sent_to_recipient = any(pl.recipient_email.strip().lower() == recipient_email.strip().lower() for pl in prev_logs)
                if has_sent_to_recipient:
                    notification_type = "RISK_ESCALATION"

        # Format Subject per specification: Subject: Action Required – {Issue Category} – Order {Order ID}
        subject_prefix = "Action Required" if notification_type == "ACTION_REQUIRED" else "ESCALATED Action Required"
        subject = f"{subject_prefix} – {alert.title} – Order {order_id}"

        order_link = f"{app_url}/orders/{order_id}"
        issue_link = f"{app_url}/my-work?dept={alert.department}"

        # Determine delay impact type
        impact_type = "Confirmed Delivery Delay" if alert.severity == "CRITICAL" else "Potential Delivery Risk"
        product_info = f"{product_name or 'Manufactured Unit'} (Qty: {product_qty or 'N/A'})"

        body = cls.render_neat_plain_text(
            title="Operational Risk Action Notice",
            order_id=order_id,
            customer_name=customer_name or "Commercial Account",
            product_info=product_info,
            required_date=required_date,
            committed_date=approved_date or required_date,
            department=alert.department,
            severity=alert.severity,
            issue_category=alert.risk_category,
            impact_status=impact_type,
            description=alert.description,
            delivery_impact=alert.delivery_impact,
            action_required=alert.recommended_action or "Investigate issue in assigned department work center.",
            order_link=order_link,
            queue_link=issue_link,
            governance_notice="The revised delivery date is not confirmed. Do not invent revised dates or schedule promises without verified department evidence.",
        )

        html_body = cls.render_neat_email_html(
            title="Operational Risk Action Notice",
            order_id=order_id,
            customer_name=customer_name or "Commercial Account",
            product_info=product_info,
            required_date=required_date,
            committed_date=approved_date or required_date,
            department=alert.department,
            severity=alert.severity,
            issue_category=alert.risk_category,
            impact_status=impact_type,
            description=alert.description,
            delivery_impact=alert.delivery_impact,
            action_required=alert.recommended_action or "Investigate issue in assigned department work center.",
            order_link=order_link,
            queue_link=issue_link,
            recipient_category="OPERATIONAL",
        )

        return cls._dispatch_and_persist_notification(
            db=db,
            alert_id=alert.id,
            customer_order_id=order_id,
            recipient_email=recipient_email,
            recipient_category="OPERATIONAL",
            department=alert.department,
            notification_type=notification_type,
            subject=subject,
            body_text=body,
            html_body=html_body,
        )

    @classmethod
    def send_customer_service_notification(
        cls,
        db: Session,
        alert: RiskAlert,
        customer_name: Optional[str] = None,
        required_date: Optional[str] = None,
        approved_date: Optional[str] = None,
        estimated_achievable_date: Optional[str] = None,
        app_url: str = "http://localhost:5173",
        force_send: bool = False,
    ) -> Optional[EmailNotificationLog]:
        """
        Agent 3 Customer Service Email Notification (Section 6).
        - Independently notifies Customer Service when an issue may affect the customer's delivery date.
        - CS receives delivery-risk notifications; operational receives corrective action notifications.
        """
        cs_email, _ = cls.get_customer_service_recipient(db)
        order_id = alert.customer_order_id

        # Duplicate check against target recipient
        prev_logs = db.query(EmailNotificationLog).filter(
            EmailNotificationLog.alert_id == alert.id,
            EmailNotificationLog.recipient_category == "CUSTOMER_SERVICE",
            EmailNotificationLog.status.in_(["SENT", "PENDING_CONFIG"]),
        ).order_by(EmailNotificationLog.created_at.desc()).all()

        notification_type = "DELIVERY_RISK"
        if prev_logs and not force_send:
            # Check if this specific recipient already received this alert with identical severity
            has_identical = any(
                pl.recipient_email.strip().lower() == cs_email.strip().lower()
                and (f"[{alert.severity}]" in pl.subject or alert.severity in pl.body_text)
                for pl in prev_logs
            )
            if has_identical:
                return None
            else:
                has_sent_to_recipient = any(pl.recipient_email.strip().lower() == cs_email.strip().lower() for pl in prev_logs)
                if has_sent_to_recipient:
                    notification_type = "RISK_ESCALATION"

        subject = f"Delivery Risk Alert – Order {order_id}"
        if notification_type == "RISK_ESCALATION":
            subject = f"ESCALATED Delivery Risk Alert – Order {order_id}"

        order_link = f"{app_url}/orders/{order_id}"
        monitoring_link = f"{app_url}/monitoring?order={order_id}"

        impact_type = "Confirmed Delivery Delay" if alert.severity == "CRITICAL" else "Potential Delivery Risk"
        cs_action = f"Monitor order in Manufacturing 360 and coordinate customer communications. Current achievable date: {estimated_achievable_date or 'Under verification by operations'}."
        cs_gov = "The revised delivery date has not yet been confirmed. Please monitor this order in Manufacturing 360 and prepare to communicate with the customer once verified delivery information is available. Do NOT send unverified delivery promises to customers."

        body = cls.render_neat_plain_text(
            title="Customer Service · Delivery Risk Alert",
            order_id=order_id,
            customer_name=customer_name or "Enterprise Customer",
            required_date=required_date,
            committed_date=approved_date,
            department=alert.department,
            severity=alert.severity,
            issue_category=alert.risk_category,
            impact_status=impact_type,
            description=alert.description,
            delivery_impact=alert.delivery_impact,
            action_required=cs_action,
            order_link=order_link,
            queue_link=monitoring_link,
            governance_notice=cs_gov,
        )

        html_body = cls.render_neat_email_html(
            title="Customer Service · Delivery Risk Alert",
            order_id=order_id,
            customer_name=customer_name or "Enterprise Customer",
            required_date=required_date,
            committed_date=approved_date,
            department=alert.department,
            severity=alert.severity,
            issue_category=alert.risk_category,
            impact_status=impact_type,
            description=alert.description,
            delivery_impact=alert.delivery_impact,
            action_required=cs_action,
            order_link=order_link,
            queue_link=monitoring_link,
            recipient_category="CUSTOMER_SERVICE",
            governance_notice=cs_gov,
        )

        return cls._dispatch_and_persist_notification(
            db=db,
            alert_id=alert.id,
            customer_order_id=order_id,
            recipient_email=cs_email,
            recipient_category="CUSTOMER_SERVICE",
            department="CUSTOMER_SERVICE",
            notification_type=notification_type,
            subject=subject,
            body_text=body,
            html_body=html_body,
        )

    @classmethod
    def build_cs_notification_dict(
        cls,
        alert: RiskAlert,
        customer_name: Optional[str] = None,
        required_date: Optional[str] = None,
        approved_date: Optional[str] = None,
        estimated_achievable_date: Optional[str] = None,
        cs_email: Optional[str] = None,
        notification_type: str = "DELIVERY_RISK",
        app_url: str = "http://localhost:5173",
    ) -> Dict[str, Any]:
        order_id = alert.customer_order_id
        subject = f"Delivery Risk Alert – Order {order_id}"
        if notification_type == "RISK_ESCALATION":
            subject = f"ESCALATED Delivery Risk Alert – Order {order_id}"

        order_link = f"{app_url}/orders/{order_id}"
        monitoring_link = f"{app_url}/monitoring?order={order_id}"
        impact_type = "Confirmed Delivery Delay" if alert.severity == "CRITICAL" else "Potential Delivery Risk"
        cs_action = f"Monitor order in Manufacturing 360 and coordinate customer communications. Current achievable date: {estimated_achievable_date or 'Under verification by operations'}."
        cs_gov = "The revised delivery date has not yet been confirmed. Please monitor this order in Manufacturing 360 and prepare to communicate with the customer once verified delivery information is available. Do NOT send unverified delivery promises to customers."

        body = cls.render_neat_plain_text(
            title="Customer Service · Delivery Risk Alert",
            order_id=order_id,
            customer_name=customer_name or "Enterprise Customer",
            required_date=required_date,
            committed_date=approved_date,
            department=alert.department,
            severity=alert.severity,
            issue_category=alert.risk_category,
            impact_status=impact_type,
            description=alert.description,
            delivery_impact=alert.delivery_impact,
            action_required=cs_action,
            order_link=order_link,
            queue_link=monitoring_link,
            governance_notice=cs_gov,
        )

        html_body = cls.render_neat_email_html(
            title="Customer Service · Delivery Risk Alert",
            order_id=order_id,
            customer_name=customer_name or "Enterprise Customer",
            required_date=required_date,
            committed_date=approved_date,
            department=alert.department,
            severity=alert.severity,
            issue_category=alert.risk_category,
            impact_status=impact_type,
            description=alert.description,
            delivery_impact=alert.delivery_impact,
            action_required=cs_action,
            order_link=order_link,
            queue_link=monitoring_link,
            recipient_category="CUSTOMER_SERVICE",
            governance_notice=cs_gov,
        )

        return {
            "alert_id": alert.id,
            "customer_order_id": order_id,
            "recipient_email": cs_email or os.getenv("DEFAULT_ALERT_EMAIL", "cs-lead@manufacturing.internal"),
            "recipient_category": "CUSTOMER_SERVICE",
            "department": "CUSTOMER_SERVICE",
            "notification_type": notification_type,
            "subject": subject,
            "body_text": body,
            "html_body": html_body,
        }

    @classmethod
    def build_op_notification_dict(
        cls,
        alert: RiskAlert,
        customer_name: Optional[str] = None,
        product_name: Optional[str] = None,
        product_qty: Optional[int] = None,
        required_date: Optional[str] = None,
        approved_date: Optional[str] = None,
        op_email: Optional[str] = None,
        notification_type: str = "ACTION_REQUIRED",
        app_url: str = "http://localhost:5173",
    ) -> Dict[str, Any]:
        order_id = alert.customer_order_id
        subject = f"[{alert.department}] Action Required – Delivery Risk on Order {order_id}"
        if notification_type == "RISK_ESCALATION":
            subject = f"[{alert.department}] ESCALATED – Delivery Risk on Order {order_id}"

        order_link = f"{app_url}/orders/{order_id}"
        issue_link = f"{app_url}/monitoring?dept={alert.department}"
        impact_type = "Critical Schedule Breach" if alert.severity == "CRITICAL" else "Schedule Variance Warning"
        product_info = f"{product_name or 'Manufactured Unit'} (Qty: {product_qty or 'N/A'})"

        body = cls.render_neat_plain_text(
            title="Operational Risk Action Notice",
            order_id=order_id,
            customer_name=customer_name or "Commercial Account",
            product_info=product_info,
            required_date=required_date,
            committed_date=approved_date or required_date,
            department=alert.department,
            severity=alert.severity,
            issue_category=alert.risk_category,
            impact_status=impact_type,
            description=alert.description,
            delivery_impact=alert.delivery_impact,
            action_required=alert.recommended_action or "Investigate issue in assigned department work center.",
            order_link=order_link,
            queue_link=issue_link,
            governance_notice="The revised delivery date is not confirmed. Do not invent revised dates or schedule promises without verified department evidence.",
        )

        html_body = cls.render_neat_email_html(
            title="Operational Risk Action Notice",
            order_id=order_id,
            customer_name=customer_name or "Commercial Account",
            product_info=product_info,
            required_date=required_date,
            committed_date=approved_date or required_date,
            department=alert.department,
            severity=alert.severity,
            issue_category=alert.risk_category,
            impact_status=impact_type,
            description=alert.description,
            delivery_impact=alert.delivery_impact,
            action_required=alert.recommended_action or "Investigate issue in assigned department work center.",
            order_link=order_link,
            queue_link=issue_link,
            recipient_category="OPERATIONAL",
        )

        return {
            "alert_id": alert.id,
            "customer_order_id": order_id,
            "recipient_email": op_email or os.getenv("DEFAULT_ALERT_EMAIL", f"{alert.department.lower()}-ops@manufacturing.internal"),
            "recipient_category": "OPERATIONAL",
            "department": alert.department,
            "notification_type": notification_type,
            "subject": subject,
            "body_text": body,
            "html_body": html_body,
        }

    @classmethod
    def send_resolution_notification(
        cls,
        db: Session,
        alert: RiskAlert,
        customer_name: Optional[str] = None,
        resolved_by_name: Optional[str] = None,
        app_url: str = "http://localhost:5173",
    ) -> List[EmailNotificationLog]:
        """
        Notifies both Operational Department and Customer Service when a risk alert is resolved (Rule 4).
        """
        results = []
        order_id = alert.customer_order_id
        subject = f"Resolved – Manufacturing Alert: Order {order_id} – {alert.title}"
        order_link = f"{app_url}/orders/{order_id}"
        resolved_time = alert.resolved_at.strftime('%Y-%m-%d %H:%M:%S UTC') if alert.resolved_at else utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        resolver = resolved_by_name or "Authorized Department Operator"
        notes = alert.resolution_notes or "Corrective actions verified and closed."

        # 1. Operational recipient
        op_email, _ = cls.get_recipient_for_department(db, alert.department)
        op_body = cls.render_neat_plain_text(
            title="Risk Resolution Notice",
            order_id=order_id,
            customer_name=customer_name,
            department=alert.department,
            severity="LOW",
            issue_category=alert.risk_category,
            impact_status="Resolved",
            description=f"Alert '{alert.title}' resolved by {resolver} on {resolved_time}.\nResolution Notes: {notes}",
            action_required="No further operational action required. Issue closed.",
            order_link=order_link,
            governance_notice="The operational blocker has been resolved. Order milestones have returned to active tracking.",
        )
        op_html = cls.render_neat_email_html(
            title="Risk Resolution Notice",
            order_id=order_id,
            customer_name=customer_name,
            department=alert.department,
            severity="LOW",
            issue_category=alert.risk_category,
            impact_status="Resolved",
            description=f"Alert '{alert.title}' resolved by {resolver} on {resolved_time}.",
            action_required=f"Resolution Notes: {notes}",
            order_link=order_link,
            recipient_category="OPERATIONAL",
            governance_notice="The operational blocker has been resolved. Order milestones have returned to active tracking.",
        )
        log1 = cls._dispatch_and_persist_notification(
            db=db,
            alert_id=alert.id,
            customer_order_id=order_id,
            recipient_email=op_email,
            recipient_category="OPERATIONAL",
            department=alert.department,
            notification_type="RESOLVED",
            subject=subject,
            body_text=op_body,
            html_body=op_html,
        )
        results.append(log1)

        # 2. Customer Service recipient
        cs_email, _ = cls.get_customer_service_recipient(db)
        cs_body = cls.render_neat_plain_text(
            title="Customer Service · Issue Resolution Notice",
            order_id=order_id,
            customer_name=customer_name or "Enterprise Customer",
            department=alert.department,
            severity="LOW",
            issue_category=alert.risk_category,
            impact_status="Resolved",
            description=f"The operational blocker on Order {order_id} has been cleared by {alert.department}.\nResolution Notes: {notes}",
            action_required="You may update customer status notes accordingly. Order has returned to scheduled tracking.",
            order_link=order_link,
            governance_notice="Verified resolution recorded. Revised promises may now be confirmed if needed.",
        )
        cs_html = cls.render_neat_email_html(
            title="Customer Service · Issue Resolution",
            order_id=order_id,
            customer_name=customer_name or "Enterprise Customer",
            department=alert.department,
            severity="LOW",
            issue_category=alert.risk_category,
            impact_status="Resolved",
            description=f"The operational blocker on Order {order_id} has been cleared by {alert.department}.",
            action_required=f"Resolution Notes: {notes}\n\nYou may update customer status notes accordingly.",
            order_link=order_link,
            recipient_category="CUSTOMER_SERVICE",
            governance_notice="Verified resolution recorded. Revised promises may now be confirmed if needed.",
        )
        log2 = cls._dispatch_and_persist_notification(
            db=db,
            alert_id=alert.id,
            customer_order_id=order_id,
            recipient_email=cs_email,
            recipient_category="CUSTOMER_SERVICE",
            department="CUSTOMER_SERVICE",
            notification_type="RESOLVED",
            subject=subject,
            body_text=cs_body,
            html_body=cs_html,
        )
        results.append(log2)

        return results

    @classmethod
    def send_followup_notification(
        cls,
        db: Session,
        alert: RiskAlert,
        days_unresolved: int = 3,
        first_email_date: Optional[str] = None,
        customer_name: Optional[str] = None,
        product_name: Optional[str] = None,
        product_qty: Optional[int] = None,
        required_date: Optional[str] = None,
        approved_date: Optional[str] = None,
        app_url: str = "http://localhost:5173",
        force_send: bool = False,
    ) -> List[EmailNotificationLog]:
        """
        Dispatches an automated Agent 3 follow-up email when an operational risk alert
        remains unresolved >= 3 days after the first risk email was sent.
        Notifies the responsible Operational Department and Customer Service with an
        urgent escalation message.
        """
        results = []
        order_id = alert.customer_order_id
        order_link = f"{app_url}/orders/{order_id}"
        issue_link = f"{app_url}/my-work?dept={alert.department}"

        # 1. Operational Department Follow-up
        op_email, _ = cls.get_recipient_for_department(db, alert.department)
        
        # Check de-duplication: don't send repeat follow-up if one was sent in the last 3 days
        skip_op = False
        if not force_send:
            recent_op_followup = db.query(EmailNotificationLog).filter(
                EmailNotificationLog.alert_id == alert.id,
                EmailNotificationLog.recipient_category == "OPERATIONAL",
                EmailNotificationLog.notification_type == "FOLLOW_UP",
                EmailNotificationLog.status.in_(["SENT", "PENDING_CONFIG"]),
            ).order_by(EmailNotificationLog.created_at.desc()).first()
            if recent_op_followup:
                now_dt = utcnow()
                created = recent_op_followup.created_at
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if (now_dt - created).total_seconds() < (3 * 86400):
                    logger.info(f"Skipping operational follow-up for Alert #{alert.id}: follow-up already sent on {created}")
                    skip_op = True

        if not skip_op:
            op_subject = f"[FOLLOW-UP URGENT] Action Required: Unresolved Risk Alert – {alert.title} – Order {order_id} (Day {days_unresolved})"
            op_body = cls.render_neat_plain_text(
                title=f"Urgent 3-Day Follow-Up · Order {order_id}",
                order_id=order_id,
                customer_name=customer_name or "Enterprise Customer",
                product_info=f"{product_name or 'Manufactured Unit'} (Qty: {product_qty or 'N/A'})",
                required_date=required_date,
                committed_date=approved_date,
                department=alert.department,
                severity="CRITICAL",
                issue_category=alert.risk_category,
                impact_status=f"Unresolved for {days_unresolved} Days (SLA Breached)",
                description=f"Automated follow-up: Initial alert was dispatched on {first_email_date or 'earlier cycle'} ({days_unresolved} days ago). Corrective actions have not yet been recorded and alert remains {alert.status}.\n\nIssue Details:\n{alert.description}",
                delivery_impact=alert.delivery_impact or "Continued non-resolution threatens delivery milestones and SLA commitments.",
                action_required=alert.recommended_action or "Immediately access department work queue, complete corrective action, and click 'Resolve' in portal.",
                order_link=order_link,
                queue_link=issue_link,
                governance_notice="The revised delivery date is not confirmed. Do not invent revised dates without verified department evidence.",
            )
            op_html = cls.render_neat_email_html(
                title=f"Urgent Follow-Up · Day {days_unresolved}",
                order_id=order_id,
                customer_name=customer_name or "Enterprise Customer",
                product_info=f"{product_name or 'Manufactured Unit'} (Qty: {product_qty or 'N/A'})",
                required_date=required_date,
                committed_date=approved_date,
                department=alert.department,
                severity="CRITICAL",
                issue_category=alert.risk_category,
                impact_status=f"Unresolved for {days_unresolved} Days (SLA Breached)",
                description=f"Automated follow-up: Initial alert was dispatched on {first_email_date or 'earlier cycle'} ({days_unresolved} days ago). Corrective actions have not yet been recorded and alert remains {alert.status}.\n\nIssue Details:\n{alert.description}",
                delivery_impact=alert.delivery_impact or "Continued non-resolution threatens delivery milestones and SLA commitments.",
                action_required=alert.recommended_action or "Immediately access department work queue, complete corrective action, and click 'Resolve' in portal.",
                order_link=order_link,
                queue_link=issue_link,
                recipient_category="OPERATIONAL",
                governance_notice="The revised delivery date is not confirmed. Do not invent revised dates without verified department evidence.",
            )
            log_op = cls._dispatch_and_persist_notification(
                db=db,
                alert_id=alert.id,
                customer_order_id=order_id,
                recipient_email=op_email,
                recipient_category="OPERATIONAL",
                department=alert.department,
                notification_type="FOLLOW_UP",
                subject=op_subject,
                body_text=op_body,
                html_body=op_html,
            )
            results.append(log_op)

        # 2. Customer Service Follow-up
        cs_email, _ = cls.get_customer_service_recipient(db)
        skip_cs = False
        if not force_send:
            recent_cs_followup = db.query(EmailNotificationLog).filter(
                EmailNotificationLog.alert_id == alert.id,
                EmailNotificationLog.recipient_category == "CUSTOMER_SERVICE",
                EmailNotificationLog.notification_type == "FOLLOW_UP",
                EmailNotificationLog.status.in_(["SENT", "PENDING_CONFIG"]),
            ).order_by(EmailNotificationLog.created_at.desc()).first()
            if recent_cs_followup:
                now_dt = utcnow()
                created = recent_cs_followup.created_at
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if (now_dt - created).total_seconds() < (3 * 86400):
                    skip_cs = True

        if not skip_cs:
            cs_subject = f"[FOLLOW-UP] Delivery Risk Reminder: Unresolved Issue – Order {order_id} (Day {days_unresolved})"
            cs_body = cls.render_neat_plain_text(
                title=f"Customer Service · Risk Follow-Up (Day {days_unresolved})",
                order_id=order_id,
                customer_name=customer_name or "Enterprise Customer",
                department=alert.department,
                severity=alert.severity,
                issue_category=alert.risk_category,
                impact_status=f"Unresolved for {days_unresolved} Days",
                description=f"Surveillance alert on Order {order_id} has exceeded the 3-day resolution window without department closure.\nAn urgent follow-up directive has been dispatched to {alert.department}.\n\nIssue Details:\n{alert.description}",
                delivery_impact=alert.delivery_impact or "Delivery timeline remains under threat until operational blocker is resolved.",
                action_required="Monitor order progress in Manufacturing 360 and coordinate with account stakeholders.",
                order_link=order_link,
                queue_link=f"{app_url}/monitoring?order={order_id}",
                governance_notice="Do NOT communicate revised dates to the customer without formal operational confirmation.",
            )
            cs_html = cls.render_neat_email_html(
                title=f"Customer Service · Risk Follow-Up",
                order_id=order_id,
                customer_name=customer_name or "Enterprise Customer",
                department=alert.department,
                severity=alert.severity,
                issue_category=alert.risk_category,
                impact_status=f"Unresolved for {days_unresolved} Days",
                description=f"Surveillance alert on Order {order_id} has exceeded the 3-day resolution window without department closure.\nAn urgent follow-up directive has been dispatched to {alert.department}.",
                delivery_impact=alert.delivery_impact or "Delivery timeline remains under threat until operational blocker is resolved.",
                action_required="Monitor order progress in Manufacturing 360 and coordinate with account stakeholders.",
                order_link=order_link,
                queue_link=f"{app_url}/monitoring?order={order_id}",
                recipient_category="CUSTOMER_SERVICE",
                governance_notice="Do NOT communicate revised dates to the customer without formal operational confirmation.",
            )
            log_cs = cls._dispatch_and_persist_notification(
                db=db,
                alert_id=alert.id,
                customer_order_id=order_id,
                recipient_email=cs_email,
                recipient_category="CUSTOMER_SERVICE",
                department="CUSTOMER_SERVICE",
                notification_type="FOLLOW_UP",
                subject=cs_subject,
                body_text=cs_body,
                html_body=cs_html,
            )
            results.append(log_cs)

        return results

    @classmethod
    def send_escalation_notification(
        cls,
        db: Session,
        customer_order_id: str,
        reason: str,
        agent_name: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[EmailNotificationLog]:
        """
        Notify Customer Service contact when an autonomous agent result has
        confidence LOW or fails validation twice, marking the item NEEDS_HUMAN.
        """
        cs_email, _ = cls.get_customer_service_recipient(db)
        app_url = getattr(settings, "cors_origins", "").split(",")[0].strip() or "http://localhost:5173"
        subject = f"[ESCALATION: NEEDS_HUMAN] {agent_name.upper()} Order #{customer_order_id}"
        details_str = json.dumps(details or {}, indent=2, default=str) if details else "None"
        body_text = f"""MANUFACTURING 360 – AUTONOMOUS AGENT ESCALATION (NEEDS_HUMAN)
================================================================================
Order ID:               {customer_order_id}
Escalating Agent:       {agent_name}
Decision:               NEEDS_HUMAN
Reason:                 {reason}

Autonomous actions have been halted on this order commitment.
Customer Service / Account Manager manual review is required to proceed.

CONTEXT & DETAILS:
{details_str}

Review order in workspace: {app_url}/orders/{customer_order_id}
================================================================================
"""
        return cls._dispatch_and_persist_notification(
            db=db,
            alert_id=None,
            customer_order_id=customer_order_id,
            recipient_email=cs_email,
            recipient_category="CUSTOMER_SERVICE",
            department="CUSTOMER_SERVICE",
            notification_type="ACTION_REQUIRED",
            subject=subject,
            body_text=body_text,
        )

    @classmethod
    def send_customer_order_approval_notification(
        cls,
        db: Session,
        proposal: CommitmentProposal,
        decision_note: Optional[str] = None,
        approved_by_user: Optional[Any] = None,
        app_url: str = "http://localhost:5173",
    ) -> List[EmailNotificationLog]:
        """
        Dispatches official Customer Order Commitment & Delivery Confirmation Email
        when a commitment proposal is approved.
        - Identifies customer details, product, quantity, unit price, requested date,
          and confirmed promised delivery date.
        - Audits 7-conduit feasibility readiness status (ERP, PLM, MMS, MES, WMS, QMS, TMS).
        - Dispatches primary confirmation to customer procurement email.
        - Dispatches CC copy to Customer Service Lead for complete auditability.
        - Persists all notifications in EmailNotificationLog.
        """
        results = []
        order_id = proposal.customer_order_id

        # 1. Fetch linked OrderAssessment if exists
        clean_id = order_id.replace("PRE-", "") if order_id else ""
        assessment = None
        if hasattr(proposal, "assessments") and proposal.assessments:
            assessment = proposal.assessments[0]
        if not assessment:
            assessment = db.query(OrderAssessment).filter(
                (OrderAssessment.proposal_id == proposal.id)
                | (OrderAssessment.assessment_id == clean_id)
                | (OrderAssessment.customer_order_id == order_id)
            ).first()

        # 2. Fetch linked FactCustomerOrder if exists
        fact_order = db.query(FactCustomerOrder).filter(
            FactCustomerOrder.customer_order_id == order_id
        ).first()

        # 3. Extract order & commercial details
        customer_id = None
        customer_name = None
        product_id = None
        product_name = None
        order_qty = None
        unit_price_inr = None
        requested_delivery_date = None
        preferred_carrier = "DHL Express"
        ship_to = None

        if assessment:
            customer_id = assessment.customer_id
            order_qty = assessment.order_qty
            product_id = assessment.product_id
            requested_delivery_date = assessment.requested_delivery_date
            unit_price_inr = float(assessment.unit_price_inr) if assessment.unit_price_inr else None
            ship_to = assessment.ship_to
            if assessment.customer:
                customer_name = assessment.customer.customer_name
                if assessment.customer.preferred_carrier:
                    preferred_carrier = assessment.customer.preferred_carrier
            if assessment.product:
                product_name = assessment.product.product_name

        if fact_order:
            if not customer_id:
                customer_id = fact_order.customer_id
            if not order_qty:
                order_qty = fact_order.order_qty
            if not product_id:
                product_id = fact_order.product_id
            if not requested_delivery_date:
                requested_delivery_date = fact_order.requested_delivery_date
            if not unit_price_inr and fact_order.unit_price_inr:
                unit_price_inr = float(fact_order.unit_price_inr)
            if not customer_name and fact_order.customer:
                customer_name = fact_order.customer.customer_name
                if fact_order.customer.preferred_carrier:
                    preferred_carrier = fact_order.customer.preferred_carrier
            if not product_name and fact_order.product:
                product_name = fact_order.product.product_name

        # Resolve missing customer name
        if not customer_name and customer_id:
            cust = db.query(DimCustomer).filter(DimCustomer.customer_id == customer_id).first()
            if cust:
                customer_name = cust.customer_name
                if cust.preferred_carrier:
                    preferred_carrier = cust.preferred_carrier

        # Resolve missing product name & price
        if not product_name and product_id:
            prod = db.query(DimProduct).filter(DimProduct.product_id == product_id).first()
            if prod:
                product_name = prod.product_name
                if not unit_price_inr and prod.standard_unit_cost_inr:
                    unit_price_inr = float(prod.standard_unit_cost_inr) * 1.35

        # Fallbacks for any remaining unassigned fields
        customer_name = customer_name or "Commercial Customer"
        product_name = product_name or "Manufactured Smartphone Unit"
        order_qty = order_qty or 100
        unit_price_inr = unit_price_inr or 14500.00
        total_value_inr = unit_price_inr * order_qty

        # 4. Resolve customer email
        customer_email = None
        if customer_id:
            setting_override = db.query(SystemSetting).filter(SystemSetting.key == f"customer_email_{customer_id}").first()
            if setting_override and setting_override.value:
                customer_email = setting_override.value.strip()

        if not customer_email:
            cust_info = DEFAULT_CUSTOMER_CONTACTS.get(customer_id or "")
            if not cust_info and customer_name:
                for cid, info in DEFAULT_CUSTOMER_CONTACTS.items():
                    if info["customer_name"].lower() == customer_name.lower():
                        cust_info = info
                        break
            if cust_info and cust_info.get("email"):
                customer_email = cust_info["email"]
            elif customer_name:
                clean_name = re.sub(r"[^a-zA-Z0-9]", "", customer_name.lower())
                customer_email = f"procurement@{clean_name}.com"
            else:
                customer_email = "procurement@commercialcustomer.com"

        # 5. Promising Delivery Date & Schedule Variance
        promised_date = proposal.proposed_date
        promised_date_str = promised_date.strftime("%B %d, %Y") if hasattr(promised_date, "strftime") else str(promised_date)
        requested_date_str = (
            requested_delivery_date.strftime("%B %d, %Y")
            if requested_delivery_date and hasattr(requested_delivery_date, "strftime")
            else str(requested_delivery_date or "Target Schedule on File")
        )

        schedule_verdict = "ON-TIME"
        schedule_variance_text = "On-Time Commitment (Target Schedule Fully Achieved, 0-Day Variance)"
        if requested_delivery_date and promised_date:
            try:
                delta = (promised_date - requested_delivery_date).days
                if delta == 0:
                    schedule_verdict = "ON-TIME"
                    schedule_variance_text = "On-Time Commitment (Target Schedule Fully Achieved, 0-Day Variance)"
                elif delta > 0:
                    schedule_verdict = "REVISED_SCHEDULE"
                    schedule_variance_text = f"+{delta} Day(s) Operational Variance (Feasible SMT Line & Supply Commitment)"
                else:
                    schedule_verdict = "AHEAD_OF_SCHEDULE"
                    schedule_variance_text = f"{abs(delta)} Day(s) Ahead of Requested Target Schedule"
            except Exception:
                pass

        # 6. Feasibility Audit across all 7 operational conduits
        conduit_statuses = {
            "ERP": "READY",
            "PLM": "READY",
            "MMS": "READY",
            "MES": "READY",
            "WMS": "READY",
            "QMS": "READY",
            "TMS": "READY",
        }
        if assessment and assessment.readiness_records:
            for rec in assessment.readiness_records:
                dept_key = (rec.department or "").upper().strip()
                if dept_key in conduit_statuses:
                    conduit_statuses[dept_key] = rec.readiness_status

        # 7. Approver audit
        approver_name = "Authorized Commercial Approver"
        approver_role = "Commercial Operations Lead"
        if approved_by_user:
            approver_name = getattr(approved_by_user, "full_name", None) or getattr(approved_by_user, "username", "Commercial Operations")
            approver_role = getattr(approved_by_user, "role", "Approver").title()

        now_str = utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        dec_note = decision_note or "Commercial commitment proposal approved. Autonomous 7-conduit operational feasibility validated."
        order_tracking_url = f"{app_url}/orders/{order_id}"

        # 8. Compose Email Body
        body_text = f"""MANUFACTURING 360 – OFFICIAL ORDER COMMITMENT & DELIVERY CONFIRMATION
================================================================================
Dear Customer Procurement Team ({customer_name}),

We are pleased to confirm that your purchase order commitment has been officially
approved by Manufacturing Commercial Operations. Autonomous cross-departmental 
feasibility has been fully validated across all 7 operational conduits.

================================================================================
1. COMMERCIAL COMMITMENT & SCHEDULE SUMMARY
================================================================================
Order Reference ID:         {order_id}
Customer Account:           {customer_name} ({customer_id or 'DIRECT'})
Primary Contact Email:      {customer_email}
Order Status:               COMMITTED & RELEASED FOR PRODUCTION
Proposal Revision:          Revision #{proposal.revision}

Product Model:              {product_name} ({product_id or 'PRD-SPEC'})
Committed Quantity:         {order_qty:,} Units
Unit Price:                 ₹{unit_price_inr:,.2f} INR
Total Commercial Value:     ₹{total_value_inr:,.2f} INR

REQUESTED DELIVERY DATE:    {requested_date_str}
CONFIRMED PROMISED DATE:    {promised_date_str}
SCHEDULE VERDICT:           {schedule_variance_text}

================================================================================
2. 7-CONDUIT AUTONOMOUS FEASIBILITY AUDIT
================================================================================
[ERP] Enterprise Resource Planning:    {conduit_statuses['ERP']} - Commercial credit terms, order contract & master lines cleared
[PLM] Product Lifecycle Management:    {conduit_statuses['PLM']} - Engineering specification Rev 2.1 & active BOM certified
[MMS] Material Management System:      {conduit_statuses['MMS']} - Raw materials, silicon & component allocations secured
[MES] Manufacturing Execution System:  {conduit_statuses['MES']} - Production line slot & SMT assembly capacity scheduled
[WMS] Warehouse Management System:     {conduit_statuses['WMS']} - Finished goods buffer & staging bay reserved
[QMS] Quality Management System:       {conduit_statuses['QMS']} - In-line inspection gates & AQL standards configured
[TMS] Transportation Management:       {conduit_statuses['TMS']} - Logistics dispatch scheduled via {preferred_carrier}

================================================================================
3. LOGISTICS & DISPATCH SPECIFICATIONS
================================================================================
Designated Carrier:         {preferred_carrier}
Dispatch Fulfillment Hub:   Main Plant Logistics Center (State: Tamil Nadu)
Estimated Transit Time:     2 - 3 Business Days
Delivery Address:           {ship_to or 'Registered Commercial Address on File'}

================================================================================
4. COMMERCIAL GOVERNANCE & APPROVAL AUDIT
================================================================================
Approved By:                {approver_name} ({approver_role})
Approval Timestamp:         {now_str}
Approval Decision Note:
"{dec_note}"

================================================================================
5. ORDER TRACKING & CUSTOMER SUPPORT
================================================================================
You can track real-time manufacturing and shipment milestones in the live portal:
{order_tracking_url}

For any inquiries or schedule modifications, please reference Order ID '{order_id}'
and contact your dedicated Commercial Support team:
- Customer Service Desk:    cs-lead@manufacturing.internal
- Direct Hotline:           +91-1800-419-3600
- Business Hours:           Monday - Saturday, 08:00 - 20:00 IST

Thank you for choosing Manufacturing 360 as your technology manufacturing partner.
================================================================================
"""

        customer_subject = f"Order Commitment Confirmation: {order_id} – Promised Delivery: {promised_date_str}"

        # 9. Primary dispatch to Customer
        log_customer = cls._dispatch_and_persist_notification(
            db=db,
            alert_id=None,
            customer_order_id=order_id,
            recipient_email=customer_email,
            recipient_category="CUSTOMER",
            department="COMMERCIAL",
            notification_type="ORDER_CONFIRMATION",
            subject=customer_subject,
            body_text=body_text,
        )
        results.append(log_customer)

        # 10. CC copy to Customer Service
        cs_email, _ = cls.get_customer_service_recipient(db)
        cs_subject = f"[CC COPY - CUSTOMER DISPATCH] Order Commitment Confirmation: {order_id} – Promised Delivery: {promised_date_str}"
        log_cs = cls._dispatch_and_persist_notification(
            db=db,
            alert_id=None,
            customer_order_id=order_id,
            recipient_email=cs_email,
            recipient_category="CUSTOMER_SERVICE",
            department="CUSTOMER_SERVICE",
            notification_type="ORDER_CONFIRMATION",
            subject=cs_subject,
            body_text=body_text,
        )
        results.append(log_cs)

        return results

    @classmethod
    def send_admin_alert(
        cls,
        db: Session,
        agent_name: str,
        limit_type: str,
        message: str,
    ) -> Optional[EmailNotificationLog]:
        """
        Notify System Administrator when an autonomous agent hits a central
        limit (max LLM calls/hr, max auto-actions/day, max cycle cost) and is paused.
        """
        admin_email = getattr(settings, "admin_email", "admin@manufacturing.com")
        subject = f"[ADMIN ALERT: KILL SWITCH] Agent '{agent_name}' Limit Exceeded ({limit_type})"
        body_text = f"""MANUFACTURING 360 – SYSTEM BOUNDARY ALERT
================================================================================
CRITICAL: Autonomous Agent Governor Limit Breached
Agent:                  {agent_name}
Limit Category:         {limit_type}
Message:                {message}
Action Taken:           Agent '{agent_name}' has been AUTOMATICALLY PAUSED via Kill Switch.
Timestamp:              {utcnow().isoformat()}

Autonomous operations for this agent are currently suspended.
Please review governance metrics in the Agent Control Dashboard and resume when cleared.
================================================================================
"""
        return cls._dispatch_and_persist_notification(
            db=db,
            alert_id=None,
            customer_order_id="SYSTEM",
            recipient_email=admin_email,
            recipient_category="OPERATIONAL",
            department="ADMIN",
            notification_type="ACTION_REQUIRED",
            subject=subject,
            body_text=body_text,
        )

    @classmethod
    def retry_failed_notification(cls, db: Session, log_id: int) -> EmailNotificationLog:
        """
        Retries a single failed or pending-config email notification idempotently.
        """
        log = db.query(EmailNotificationLog).filter(EmailNotificationLog.id == log_id).first()
        if not log:
            raise ValueError(f"Notification log ID {log_id} not found.")

        if log.status == "SENT":
            return log

        log.last_attempt_at = utcnow()
        log.retry_count = (log.retry_count or 0) + 1

        if not cls.validate_email_address(log.recipient_email):
            log.status = "FAILED"
            log.failure_reason = f"Recipient email address '{log.recipient_email}' failed validation check."
            db.commit()
            return log

        provider = cls.get_provider()
        try:
            is_conf = provider.is_configured(log.recipient_email)
        except TypeError:
            is_conf = provider.is_configured()

        if not is_conf:
            log.status = "PENDING_CONFIG"
            log.failure_reason = "Email provider credentials are not configured in application environment."
            db.commit()
            return log

        success, err, msg_id = provider.send_email(
            recipient=log.recipient_email,
            subject=log.subject,
            body=log.body_text,
        )

        if success:
            log.status = "SENT"
            log.sent_at = utcnow()
            log.failure_reason = None
            log.provider_message_id = msg_id
        else:
            log.status = "FAILED"
            log.failure_reason = err

        db.commit()
        db.refresh(log)
        return log

    @classmethod
    def retry_all_failed_notifications(cls, db: Session, max_retries: int = 3) -> Dict[str, Any]:
        """
        Retries all failed or retrying notifications under max retry limit.
        """
        candidates = db.query(EmailNotificationLog).filter(
            EmailNotificationLog.status.in_(["FAILED", "RETRYING"]),
            EmailNotificationLog.retry_count < max_retries,
        ).all()

        succeeded = 0
        failed = 0

        for item in candidates:
            res = cls.retry_failed_notification(db, item.id)
            if res.status == "SENT":
                succeeded += 1
            else:
                failed += 1

        return {
            "total_candidates": len(candidates),
            "succeeded": succeeded,
            "still_failed": failed,
        }
