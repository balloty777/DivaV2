from datetime import datetime
from uuid import UUID,uuid4
from sqlalchemy import DateTime,ForeignKey,func,String,BigInteger
from sqlalchemy.orm import Mapped,mapped_column,relationship
from database.db import Base

class Conversation(Base):
    __tablename__="conversations"
    conversation_id:Mapped[UUID]=mapped_column(
        primary_key=True,
        default=uuid4
    )
    user_id:Mapped[UUID]=mapped_column(
        ForeignKey("users.user_id",ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    character_id:Mapped[UUID]=mapped_column(
        ForeignKey("characters.character_id",ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    title:Mapped[str|None]=mapped_column(
        String(200),
        nullable=True
    )
    status:Mapped[str]=mapped_column(
        String(20),
        nullable=False,
        default="active"
    )
    last_seq:Mapped[int]=mapped_column(
        BigInteger,
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
    user: Mapped["User"] = relationship(
        back_populates="conversations"
    )
    character:Mapped["Character"]=relationship(
        back_populates="conversations"
    )
    messages:Mapped[list["Message"]]=relationship(
        back_populates="conversation",
        cascade="all, delete-orphan"
    )
    character_summary:Mapped["ConversationCharacterSummary"]=relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        uselist=False
    )
    short_term_memory:Mapped["ShortTermMemory | None"]=relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        uselist=False
    )
    long_term_memory:Mapped["LongTermMemory | None"]=relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        uselist=False
    )