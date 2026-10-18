from database.db import Base
from datetime import datetime
from sqlalchemy.orm import mapped_column,Mapped,relationship
from sqlalchemy import DateTime,ForeignKey,func,String
from uuid import UUID,uuid4

class Character(Base):
    __tablename__='characters'
    character_id:Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    creator_id:Mapped[UUID|None]=mapped_column(ForeignKey("users.user_id",ondelete="SET NULL"),nullable=True,index=True)
    name:Mapped[str]=mapped_column(String(100),nullable=False)
    status:Mapped[str]=mapped_column(String(40),nullable=False,default="draft")
    version:Mapped[int]=mapped_column(nullable=False,default=1,server_default="1")
    avatar_url:Mapped[str|None]=mapped_column(String(500),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now())
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())
    creator:Mapped["User | None"]=relationship(
        back_populates="characters"
    )
    conversations:Mapped[list["Conversation"]]=relationship(back_populates="character")
    character_summary:Mapped["CharacterSummary"]=relationship(
        back_populates="character",
        cascade="all, delete-orphan",
        uselist=False
    )