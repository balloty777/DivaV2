from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from models.conversation import Conversation


class ConversationRepository:
    def __init__(self, db: Session):
        self.db = db
    def create_conversation(self,user_id: UUID,character_id: UUID) -> Conversation:
        conversation = Conversation(user_id=user_id,character_id=character_id)
        self.db.add(conversation)
        return conversation
    def get_by_id(self,user_id:UUID,conversation_id: UUID) -> Conversation | None:
        stmt = select(Conversation).where(Conversation.conversation_id == conversation_id,Conversation.user_id==user_id)
        return self.db.scalar(stmt)
    def get_by_user_id(self, user_id: UUID) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id,)
            .order_by(Conversation.updated_at.desc())
        )
        return list(self.db.scalars(stmt).all())
    def delete_conversation(self,conversation: Conversation) -> None:
        self.db.delete(conversation)
