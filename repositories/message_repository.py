from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from exceptions.application import NotFoundException, ConflictException
from models.conversation import Conversation
from models.message import Message

class MessageRepository:
    def __init__(self, db: Session):
        self.db = db
    def store_message(self,conversation_id: UUID,content: str,role: str) -> Message:
        stmt = (select(Conversation).where(Conversation.conversation_id == conversation_id).with_for_update().execution_options(populate_existing=True))
        conversation = self.db.scalar(stmt)
        if conversation is None:
            raise NotFoundException("Conversation does not exist")
        conversation.last_seq += 1
        self.db.flush()
        message = Message(conversation_id=conversation_id,seq=conversation.last_seq,content=content,role=role)
        self.db.add(message)
        return message
    def get_message_by_id(self, message_id: UUID) -> Message | None:
        return self.db.get(Message, message_id)
    def get_message_by_conversation_id(self,conversation_id: UUID) -> list[Message]:
        stmt = (select(Message).where(Message.conversation_id == conversation_id).order_by(Message.seq.asc()))
        return list(self.db.scalars(stmt).all())
    def get_recent(self,conversation_id: UUID,limit: int = 20) -> list[Message]:
        if limit < 1:
            raise ConflictException("Limit must be at least 1")
        stmt = (select(Message).where(Message.conversation_id == conversation_id).order_by(Message.seq.desc()).limit(limit))
        messages = list(self.db.scalars(stmt).all())
        messages.reverse()
        return messages
    def get_message_by_role(self,conversation_id: UUID,role: str) -> list[Message]:
        stmt = (select(Message).where(Message.role == role,Message.conversation_id == conversation_id).order_by(Message.seq.asc()))
        return list(self.db.scalars(stmt).all())
    def get_message_page(self,conversation_id: UUID,limit: int = 20,before_seq: int | None = None) -> list[Message]:
        if limit < 1:
            raise ConflictException("Limit must be at least 1")
        stmt = select(Message).where(Message.conversation_id == conversation_id)
        if before_seq is not None:
            stmt = stmt.where(Message.seq < before_seq)
        stmt = stmt.order_by(Message.seq.desc()).limit(limit)
        messages = list(self.db.scalars(stmt).all())
        messages.reverse()
        return messages
    def delete_message(self, message: Message) -> None:
        self.db.delete(message)