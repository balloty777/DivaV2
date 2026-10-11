from datetime import datetime
from uuid import UUID,uuid4
from sqlalchemy import DateTime,ForeignKey,String,func,Index,CheckConstraint
from sqlalchemy.orm import Mapped,mapped_column
from database.db import Base

class MemoryJob(Base):
    __tablename__="memory_jobs"
    __table_args__=(CheckConstraint("status IN ('pending','processing','completed','failed')",name="ck_memory_jobs_status"),Index("ix_memory_jobs_status_created_at","status","created_at"))

    job_id:Mapped[UUID]=mapped_column(
        primary_key=True,
        default=uuid4
    )
    conversation_id:Mapped[UUID]=mapped_column(
        ForeignKey("conversations.conversation_id",ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    through_seq:Mapped[int]=mapped_column(
        nullable=False
    )
    status:Mapped[str]=mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending"
    )
    attempts:Mapped[int]=mapped_column(
        nullable=False,
        default=0,
        server_default="0"
    )
    created_at:Mapped[datetime]=mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at:Mapped[datetime]=mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )
