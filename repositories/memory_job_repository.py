from uuid import UUID
from sqlalchemy.orm import Session
from models.memory_job import MemoryJob
from datetime import datetime,timedelta,timezone
from sqlalchemy import or_,select
from models.conversation import Conversation
from exceptions.application import NotFoundException

LEASE_DURATION=timedelta(minutes=5)

class MemoryJobRepository:
    def __init__(self,db:Session):
        self.db=db
    def create(self,conversation_id:UUID,through_seq:int)->MemoryJob:
        conversation=self.db.scalar(select(Conversation).where(Conversation.conversation_id==conversation_id).with_for_update())
        if conversation is None:
            raise NotFoundException("Conversation does not exist")
        existing=self.db.scalar(select(MemoryJob).where(MemoryJob.conversation_id==conversation_id,MemoryJob.status.in_(("pending","processing"))).order_by(MemoryJob.created_at.desc()).limit(1).with_for_update())
        if existing is not None:
            existing.through_seq=max(existing.through_seq,through_seq)
            self.db.flush()
            return existing
        job=MemoryJob(conversation_id=conversation_id,through_seq=through_seq,status="pending",attempts=0)
        self.db.add(job)
        self.db.flush()
        return job
    def claim_next_job(self)->MemoryJob|None:
        now=datetime.now(timezone.utc)
        expired_before=now-LEASE_DURATION
        stmt = (
            select(MemoryJob)
            .where(
                MemoryJob.attempts < MemoryJob.max_attempts,
                or_(
                    (
                        (MemoryJob.status == "pending")
                        & (
                            (MemoryJob.next_attempt_at.is_(None))
                            | (MemoryJob.next_attempt_at <= now)
                        )
                    ),
                    (
                        (MemoryJob.status == "processing")
                        & (
                            (MemoryJob.locked_at.is_(None))
                            | (MemoryJob.locked_at <= expired_before)
                        )
                    ),
                ),
            )
            .order_by(MemoryJob.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job=self.db.scalar(stmt)
        if job is None:
            return None
        job.status="processing"
        job.locked_at=now
        job.attempts += 1
        self.db.flush()
        return job