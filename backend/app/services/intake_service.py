import logging
import os
import threading
import time
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..config import settings
from ..database import SessionLocal
from ..models.auth import User
from ..models.business import FactCustomerOrder
from ..models.workflow import OrderAssessment
from .lease_service import DistributedSchedulerLeaseManager, get_worker_id
from .feasibility_service import FeasibilityService

logger = logging.getLogger("manufacturing.intake_watcher")

_INTAKE_LOCK = threading.Lock()


def get_or_create_system_user(db: Session, username: str = "agent2-system") -> User:
    """Ensure the system user identity exists for automated Agent 2 intake assessments."""
    email = f"{username}@manufacturing.internal"
    user = db.query(User).filter(
        or_(User.email == email, User.email == username)
    ).first()
    if not user:
        import os
        import uuid
        from .auth_service import hash_password
        system_secret = os.getenv("SYSTEM_USER_PASSWORD") or uuid.uuid4().hex
        user = User(
            email=email,
            full_name="Agent 2 Autonomous Intake System",
            hashed_password=hash_password(system_secret),
            role="operational",
            department="ERP",
            can_approve_commitments=False,
            is_active=True,
            customer_scope=None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


class BackgroundIntakeWatcher:
    """
    Background intake watcher for Agent 2 (Feasibility & Commitment Agent).
    - Periodically scans for new demand (orders with status NEW/OPEN without an assessment).
    - Automatically assesses feasibility and submits proposals for human approval.
    - Idempotent: Never creates duplicate assessments for the same order.
    - Distributed DB lease ensures only one worker polls at a time.
    """

    def __init__(
        self,
        poll_interval_seconds: Optional[int] = None,
        enabled: Optional[bool] = None,
    ):
        if poll_interval_seconds is None:
            raw_interval = os.environ.get("INTAKE_POLL_SECONDS")
            if raw_interval is not None:
                poll_interval_seconds = int(raw_interval)
            else:
                poll_interval_seconds = getattr(settings, "intake_poll_seconds", 300)

        if enabled is None:
            raw_enabled = os.environ.get("AGENT2_AUTONOMOUS_ENABLED")
            if raw_enabled is not None:
                enabled = raw_enabled.strip().lower() in ("true", "1", "yes", "on")
            else:
                enabled = getattr(settings, "agent2_autonomous_enabled", False)

        self.poll_interval_seconds = poll_interval_seconds
        self.enabled = enabled
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if not self.enabled:
            logger.info("Agent 2 Autonomous Intake Watcher disabled by configuration (AGENT2_AUTONOMOUS_ENABLED=False).")
            return
        if self.poll_interval_seconds <= 0:
            logger.info("Agent 2 Autonomous Intake Watcher disabled by configuration (INTAKE_POLL_SECONDS <= 0).")
            return
        if self._thread and self._thread.is_alive():
            logger.info("Agent 2 Intake Watcher thread already active.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="Agent2IntakeWatcher")
        self._thread.start()
        logger.info(
            f"Agent 2 Intake Watcher started with worker ID: {get_worker_id()} "
            f"(Interval: {self.poll_interval_seconds}s, Enabled: {self.enabled})."
        )

    def stop(self):
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join(timeout=3)
            logger.info("Agent 2 Intake Watcher thread stopped.")

    def _run_loop(self):
        logger.info(f"Agent 2 Intake loop initialized. Interval: {self.poll_interval_seconds}s.")
        # Brief pause on startup
        for _ in range(min(15, self.poll_interval_seconds)):
            if self._stop_event.is_set():
                return
            time.sleep(1)

        while not self._stop_event.is_set():
            self._execute_poll_cycle()
            for _ in range(self.poll_interval_seconds):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    def _execute_poll_cycle(self):
        db = SessionLocal()
        try:
            self.poll_new_orders(db)
        except Exception as e:
            logger.error(f"Agent 2 Intake Watcher cycle encountered exception: {e}", exc_info=True)
        finally:
            db.close()

    @classmethod
    def poll_new_orders(
        cls,
        db: Session,
        force_lease: bool = False,
        poll_interval_seconds: Optional[int] = None,
        enabled: Optional[bool] = None,
    ) -> List[OrderAssessment]:
        """
        Scans for NEW or OPEN customer orders without existing assessments,
        evaluates feasibility, and submits commitment proposals for human approval.
        Uses distributed DB lease for mutual exclusion.
        """
        # Determine effective enabled/interval states
        eff_interval = (
            poll_interval_seconds
            if poll_interval_seconds is not None
            else int(os.environ.get("INTAKE_POLL_SECONDS", getattr(settings, "intake_poll_seconds", 300)))
        )
        eff_enabled = (
            enabled
            if enabled is not None
            else os.environ.get("AGENT2_AUTONOMOUS_ENABLED", str(getattr(settings, "agent2_autonomous_enabled", False))).strip().lower() in ("true", "1", "yes", "on")
        )

        if not eff_enabled or eff_interval <= 0:
            logger.debug("Agent 2 intake poller is disabled by configuration (AGENT2_AUTONOMOUS_ENABLED=False or INTAKE_POLL_SECONDS <= 0).")
            return []

        if not _INTAKE_LOCK.acquire(blocking=False):
            logger.debug("Agent 2 intake local lock held by another thread; skipping poll.")
            return []

        lease_acquired, lease_reason = DistributedSchedulerLeaseManager.acquire_lease(
            db, lease_name="AGENT2_INTAKE_POLLER", lease_duration_seconds=eff_interval, force=force_lease
        )
        if not lease_acquired:
            _INTAKE_LOCK.release()
            logger.info(f"Agent 2 intake poll skipped: {lease_reason}")
            return []

        exec_status = "SUCCESS"
        exec_summary = ""
        results: List[OrderAssessment] = []

        try:
            system_user = get_or_create_system_user(db, username="agent2-system")

            # Collect all orders already assessed to prevent duplicate assessments
            existing_assessed_ids = {
                r[0] for r in db.query(OrderAssessment.customer_order_id).filter(
                    OrderAssessment.customer_order_id.isnot(None)
                ).all()
            }
            assessed_set = set()
            for oid in existing_assessed_ids:
                assessed_set.add(oid)
                if oid.startswith("PRE-"):
                    assessed_set.add(oid[4:])

            # Find new demand: orders with status NEW or OPEN that have no assessment yet
            candidate_orders = (
                db.query(FactCustomerOrder)
                .filter(FactCustomerOrder.order_status.in_(["NEW", "OPEN"]))
                .all()
            )

            unassessed_orders = [o for o in candidate_orders if o.customer_order_id not in assessed_set]
            logger.info(f"Agent 2 intake watcher identified {len(unassessed_orders)} unassessed orders.")

            for ord_item in unassessed_orders:
                try:
                    assessment = FeasibilityService.assess_new_order(
                        db=db,
                        customer_id=ord_item.customer_id,
                        product_id=ord_item.product_id,
                        order_qty=ord_item.order_qty,
                        requested_delivery_date=ord_item.requested_delivery_date,
                        user=system_user,
                        unit_price_inr=float(ord_item.unit_price_inr) if ord_item.unit_price_inr else None,
                        priority=ord_item.priority or "MEDIUM",
                        channel=ord_item.channel or "EDI",
                        submit_for_approval=True,
                        customer_order_id=ord_item.customer_order_id,
                    )
                    results.append(assessment)
                    assessed_set.add(ord_item.customer_order_id)
                except Exception as ex:
                    logger.error(f"Error assessing intake order {ord_item.customer_order_id}: {ex}", exc_info=True)

            exec_summary = f"Assessed {len(results)} new orders autonomously."
            return results
        except Exception as e:
            exec_status = "FAILURE"
            exec_summary = f"Agent 2 intake poller error: {str(e)}"
            logger.error(exec_summary, exc_info=True)
            return results
        finally:
            DistributedSchedulerLeaseManager.release_lease(
                db, lease_name="AGENT2_INTAKE_POLLER", status=exec_status, summary=exec_summary
            )
            _INTAKE_LOCK.release()


# Singleton background intake watcher instance
intake_watcher = BackgroundIntakeWatcher()
