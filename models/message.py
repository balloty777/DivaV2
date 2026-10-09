from database.db import Base
from datetime import datetime
from sqlalchemy import DateTime,ForeignKey,func,String,Text,BigInteger,CheckConstraint,UniqueConstraint,Index,text
from sqlalchemy.orm import Mapped,mapped_column,relationship
from uuid import UUID,uuid4

class Message(Base):
    __tablename__="messages"
    __table_args__=(
        UniqueConstraint("conversation_id","seq",name="uq_messages_conversation_id_seq"),
        CheckConstraint("role IN ('user','assistant')",name="ck_messages_role"),
        Index("ix_messages_conversation_id_seq_desc","conversation_id",text("seq DESC"))
    )
    message_id:Mapped[UUID]=mapped_column(
        primary_key=True,
        default=uuid4
    )
    conversation_id:Mapped[UUID]=mapped_column(
        ForeignKey(
            "conversations.conversation_id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )
    seq: Mapped[int]=mapped_column(
        BigInteger,
        nullable=False
    )
    content:Mapped[str]=mapped_column(
        Text    ,
        nullable=False
    )
    role:Mapped[str]=mapped_column(
        String(20),
        nullable=False
    )
    created_at:Mapped[datetime]=mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    conversation:Mapped["Conversation"]=relationship(
        back_populates="messages"
    )