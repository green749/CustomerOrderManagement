import logging
import threading
import time
from typing import Optional

from ..database import SessionLocal
from .lease_service import DistributedSchedulerLeaseManager, get_worker_id
from .monitoring_service import MonitoringService

logger = logging.getLogger("manufacturing.scheduler")


class BackgroundMonitoringScheduler:
    """
    Hardened distributed scheduler for Agent 3 daily monitoring runs.
    - Uses distributed DB lease to prevent duplicate runs across multi-worker deployments.
    - Recovers safely from server reboots and stale crashes.
    - Safe start / stop lifecycle tied to FastAPI lifespan.
    """

    def __init__(self, interval_seconds: Optional[int] = None):
        import os
        from ..config import settings
        if interval_seconds is None:
            raw = os.environ.get("MONITORING_INTERVAL_SECONDS")
            if raw is not None:
                interval_seconds = int(raw)
            else:
                interval_seconds = getattr(settings, "monitoring_interval_seconds", 86400)
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self.interval_seconds <= 0:
            logger.info("Background monitoring scheduler disabled by configuration (interval <= 0) to preserve Neon compute.")
            return
        if self._thread and self._thread.is_alive():
            logger.info("Scheduler thread already active.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="OrderMonitoringScheduler")
        self._thread.start()
        logger.info(f"OrderMonitoringScheduler started with worker ID: {get_worker_id()} (Interval: {self.interval_seconds}s).")

    def stop(self):
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join(timeout=3)
            logger.info("OrderMonitoringScheduler thread stopped.")

    def _run_loop(self):
        logger.info(f"Scheduler loop initialized. Interval: {self.interval_seconds}s. Initial pause to preserve Neon cold start.")
        # Initial gentle pause (30s) so fast reboot doesn't spam DB compute
        for _ in range(min(30, self.interval_seconds)):
            if self._stop_event.is_set():
                return
            time.sleep(1)

        while not self._stop_event.is_set():
            self._execute_cycle()
            # Sleep in 1-second slices so stop_event is instantly responsive
            for _ in range(self.interval_seconds):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    def _execute_cycle(self):
        db = SessionLocal()
        try:
            # Enforce 24-hour interval: if a cycle was already completed within interval_seconds, skip redundant run
            from datetime import datetime, timezone
            from ..models.workflow import MonitoringExecutionLog
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            last_run = (
                db.query(MonitoringExecutionLog)
                .filter(MonitoringExecutionLog.status == "SUCCESS")
                .order_by(MonitoringExecutionLog.executed_at.desc())
                .first()
            )
            if last_run and last_run.executed_at:
                elapsed = (now_utc - last_run.executed_at).total_seconds()
                if elapsed < (self.interval_seconds - 300):
                    logger.info(
                        f"Agent 3 scheduled run skipped: last daily run was {elapsed/3600:.1f}h ago "
                        f"(scheduled once every 24 hours / {self.interval_seconds}s)."
                    )
                    return

            log = MonitoringService.run_daily_monitoring_cycle(db, cycle_type="SCHEDULED")
            logger.info(f"Scheduled 24h monitoring run result: [{log.status}] {log.summary}")
        except Exception as e:
            logger.error(f"Scheduled monitoring run encountered exception: {e}", exc_info=True)
        finally:
            db.close()


# Singleton scheduler instance (uses MONITORING_INTERVAL_SECONDS from env/settings or defaults to 86400 / 24h)
scheduler = BackgroundMonitoringScheduler()
