from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session
from exceptions.application import NotFoundException
from models.conversation import Conversation
from models.memory_job import MemoryJob

LEASE_DURATION = timedelta(minutes=5)
BASE_RETRY_DELAY_SECONDS = 5
MAX_RETRY_DELAY_SECONDS = 15 * 60

class MemoryJobRepository:
    def __init__(self, db: Session):
        self.db = db
    def create(self, conversation_id: UUID, through_seq: int) -> MemoryJob:
        conversation = self.db.scalar(select(Conversation).where(Conversation.conversation_id == conversation_id).with_for_update())
        if conversation is None:
            raise NotFoundException("Conversation does not exist")
        existing = self.db.scalar(select(MemoryJob).where(MemoryJob.conversation_id == conversation_id,MemoryJob.status.in_(("pending", "processing"))).order_by(MemoryJob.created_at.desc()).limit(1).with_for_update())
        if existing is not None:
            existing.through_seq = max(existing.through_seq, through_seq)
            self.db.flush()
            return existing
        job = MemoryJob(conversation_id=conversation_id,through_seq=through_seq,status="pending",attempts=0)
        self.db.add(job)
        self.db.flush()
        return job
    def claim_next_job(self) -> MemoryJob | None:
        now = datetime.now(timezone.utc)
        expired_before = now - LEASE_DURATION
        self.db.execute(update(MemoryJob).where(MemoryJob.status == "processing",MemoryJob.attempts >= MemoryJob.max_attempts,or_(MemoryJob.locked_at.is_(None),MemoryJob.locked_at <= expired_before)).values(status="failed",locked_at=None,last_error="Worker lease expired after maximum attempts",next_attempt_at=None))
        self.db.flush()
        stmt = (select(MemoryJob).where(MemoryJob.attempts < MemoryJob.max_attempts,or_(((MemoryJob.status == "pending")& (MemoryJob.next_attempt_at.is_(None)| (MemoryJob.next_attempt_at <= now))),((MemoryJob.status == "processing")& (MemoryJob.locked_at.is_(None)| (MemoryJob.locked_at <= expired_before))))).order_by(MemoryJob.created_at.asc()).limit(1).with_for_update(skip_locked=True))
        job = self.db.scalar(stmt)
        if job is None:
            return None
        job.status = "processing"
        job.locked_at = now
        job.attempts += 1
        job.next_attempt_at = None
        self.db.flush()
        return job
    def mark_completed(self,job_id: UUID,processed_through_seq: int) -> bool:
        job = self.db.scalar(select(MemoryJob).where(MemoryJob.job_id == job_id).with_for_update())
        if job is None:
            raise NotFoundException("Memory job does not exist")
        if job.status != "processing":
            return False
        if job.through_seq > processed_through_seq:
            job.status = "pending"
            job.locked_at = None
            job.next_attempt_at = None
            self.db.flush()
            return False
        job.status = "completed"
        job.locked_at = None
        job.next_attempt_at = None
        job.last_error = None
        self.db.flush()
        return True
    def mark_failed(self, job_id: UUID, error: Exception | str) -> MemoryJob:
        job = self.db.scalar(select(MemoryJob).where(MemoryJob.job_id == job_id).with_for_update())
        if job is None:
            raise NotFoundException("Memory job does not exist")
        if job.status != "processing":
            return job
        now = datetime.now(timezone.utc)
        error_text = str(error)[:4000]
        job.last_error = error_text
        job.locked_at = None
        if job.attempts >= job.max_attempts:
            job.status = "failed"
            job.next_attempt_at = None
        else:
            delay = min(BASE_RETRY_DELAY_SECONDS * (2 ** (job.attempts - 1)),MAX_RETRY_DELAY_SECONDS)
            job.status = "pending"
            job.next_attempt_at = now + timedelta(seconds=delay)
        self.db.flush()
        return job