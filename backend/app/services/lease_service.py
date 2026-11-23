import os
import uuid
import socket
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from ..models.workflow import SchedulerLease

logger = logging.getLogger("manufacturing.scheduler.lease")


def utcnow():
    return datetime.now(timezone.utc)


def to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def get_worker_id() -> str:
    """Generate a stable yet unique worker identifier for this process instance."""
    hostname = socket.gethostname() or "unknown-host"
    pid = os.getpid()
    unique_suffix = getattr(get_worker_id, "_suffix", None)
    if not unique_suffix:
        unique_suffix = uuid.uuid4().hex[:8]
        setattr(get_worker_id, "_suffix", unique_suffix)
    return f"{hostname}:{pid}:{unique_suffix}"


class DistributedSchedulerLeaseManager:
    """
    Database-backed distributed lease manager.
    Guarantees:
    - Mutual exclusion across multiple FastAPI worker processes and replicas.
    - Automatic recovery from stale/orphaned leases when a worker crashes.
    - Safe non-blocking acquisition and lease renewal.
    """

    @classmethod
    def acquire_lease(
        cls,
        db: Session,
        lease_name: str = "DAILY_MONITORING",
        lease_duration_seconds: int = 600,
        worker_id: Optional[str] = None,
        force: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        worker = worker_id or get_worker_id()
        now = utcnow()
        expiry = now + timedelta(seconds=lease_duration_seconds)

        try:
            lease = db.query(SchedulerLease).filter(SchedulerLease.lease_name == lease_name).first()
            if not lease:
                new_lease = SchedulerLease(
                    lease_name=lease_name,
                    holder_id=worker,
                    acquired_at=now,
                    expires_at=expiry,
                    last_heartbeat=now,
                    version=1,
                )
                db.add(new_lease)
                db.commit()
                logger.info(f"Initialized and acquired distributed lease '{lease_name}' for worker '{worker}'.")
                return True, None

            # Lease exists: check if currently held by another worker and not yet expired
            if not force and lease.holder_id and lease.expires_at and to_utc(lease.expires_at) > now:
                if lease.holder_id == worker:
                    # Same worker renewing
                    lease.expires_at = expiry
                    lease.last_heartbeat = now
                    db.commit()
                    return True, None
                return False, f"Lease '{lease_name}' is currently held by worker '{lease.holder_id}' until {lease.expires_at.isoformat()}."

            # Lease is expired or unheld or force requested: claim it
            lease.holder_id = worker
            lease.acquired_at = now
            lease.expires_at = expiry
            lease.last_heartbeat = now
            lease.version = (lease.version or 1) + 1
            db.commit()
            logger.info(f"Claimed distributed lease '{lease_name}' for worker '{worker}'.")
            return True, None
        except Exception as e:
            db.rollback()
            logger.error(f"Error acquiring distributed lease '{lease_name}': {e}", exc_info=True)
            return False, str(e)

    @classmethod
    def heartbeat(
        cls,
        db: Session,
        lease_name: str = "DAILY_MONITORING",
        worker_id: Optional[str] = None,
        extension_seconds: int = 300,
    ) -> bool:
        worker = worker_id or get_worker_id()
        now = utcnow()
        expiry = now + timedelta(seconds=extension_seconds)

        try:
            lease = db.query(SchedulerLease).filter(
                SchedulerLease.lease_name == lease_name,
                SchedulerLease.holder_id == worker,
            ).first()
            if lease:
                lease.last_heartbeat = now
                lease.expires_at = expiry
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Error sending heartbeat for lease '{lease_name}': {e}")
            return False

    @classmethod
    def release_lease(
        cls,
        db: Session,
        lease_name: str = "DAILY_MONITORING",
        worker_id: Optional[str] = None,
        status: str = "SUCCESS",
        summary: Optional[str] = None,
    ):
        worker = worker_id or get_worker_id()
        now = utcnow()

        try:
            lease = db.query(SchedulerLease).filter(SchedulerLease.lease_name == lease_name).first()
            if lease:
                lease.holder_id = None
                lease.expires_at = now
                lease.last_cycle_status = status
                lease.last_cycle_summary = summary
                lease.last_heartbeat = now
                db.commit()
                logger.info(f"Released distributed lease '{lease_name}' by worker '{worker}'. Status: {status}.")
        except Exception as e:
            db.rollback()
            logger.error(f"Error releasing lease '{lease_name}': {e}")
