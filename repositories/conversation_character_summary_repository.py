from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from models.conversation_character_summary import ConversationCharacterSummary


class ConversationCharacterSummaryRepository:
    def __init__(self, db: Session):
        self.db = db
    def create_conversation_character_summary(self,conversation_id: UUID,content: dict) -> ConversationCharacterSummary:
        summary = ConversationCharacterSummary(conversation_id=conversation_id,content=content)
        self.db.add(summary)
        return summary
    def get_by_conversation_id(self,conversation_id: UUID) -> ConversationCharacterSummary | None:
        stmt = select(ConversationCharacterSummary).where(ConversationCharacterSummary.conversation_id == conversation_id)
        return self.db.scalar(stmt)
    def get_by_conversation_id_for_update(self,conversation_id: UUID) -> ConversationCharacterSummary | None:
        stmt = select(ConversationCharacterSummary).where(ConversationCharacterSummary.conversation_id == conversation_id).with_for_update()
        return self.db.scalar(stmt)
    def update_conversation_character_summary(self,summary: ConversationCharacterSummary,content: dict) -> ConversationCharacterSummary:
        summary.content = content
        return summary
    def delete_conversation_character_summary(self,summary: ConversationCharacterSummary) -> None:
        self.db.delete(summary)