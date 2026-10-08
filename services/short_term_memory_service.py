from uuid import UUID
from sqlalchemy.orm import Session
from repositories.short_term_memory_repository import ShortTermMemoryRepository
from models.short_term_memory import ShortTermMemory
from repositories.conversation_repository import ConversationRepository
from exceptions.application import NotFoundException, ConflictException

class ShortTermMemoryService:
    def __init__(self, db: Session):
        self.db = db
        self.short_term_memory_repository = ShortTermMemoryRepository(db)
        self.conversation_repository = ConversationRepository(db)
    def create_short_term_memory(self,user_id: UUID,conversation_id: UUID,content: dict) -> ShortTermMemory:
        conversation = self.conversation_repository.get_by_id(user_id=user_id,conversation_id=conversation_id)
        if conversation is None:
            raise NotFoundException("Conversation does not exist")
        memory = self.short_term_memory_repository.get_memory_by_conversation_id(conversation_id=conversation_id)
        if memory is not None:
            raise ConflictException("Memory for this conversation already exist")
        stm = self.short_term_memory_repository.create_short_term_memory(conversation_id=conversation_id,content=content)
        try:
            self.db.commit()
            self.db.refresh(stm)
            return stm
        except Exception:
            self.db.rollback()
            raise
    def get_short_term_memory(self,user_id: UUID,conversation_id: UUID) -> ShortTermMemory:
        conversation = self.conversation_repository.get_by_id(user_id=user_id,conversation_id=conversation_id)
        if conversation is None:
            raise NotFoundException("Conversation does not exist")
        memory = self.short_term_memory_repository.get_memory_by_conversation_id(conversation_id=conversation_id)
        if memory is None:
            raise NotFoundException("Short term memory does not exist")
        return memory
    def update_short_term_memory(self,user_id: UUID,conversation_id: UUID,content: dict) -> ShortTermMemory:
        conversation = self.conversation_repository.get_by_id(user_id=user_id,conversation_id=conversation_id)
        if conversation is None:
            raise NotFoundException("Conversation does not exist")
        memory = self.short_term_memory_repository.get_memory_by_conversation_id(conversation_id=conversation_id)
        if memory is None:
            raise NotFoundException("Short term memory does not exist")
        memory = self.short_term_memory_repository.update_short_term_memory(memory=memory,content=content)
        try:
            self.db.commit()
            self.db.refresh(memory)
            return memory
        except Exception:
            self.db.rollback()
            raise
    def delete_short_term_memory(self,user_id: UUID,conversation_id: UUID) -> None:
        conversation = self.conversation_repository.get_by_id(user_id=user_id,conversation_id=conversation_id)
        if conversation is None:
            raise NotFoundException("Conversation does not exist")
        memory = self.short_term_memory_repository.get_memory_by_conversation_id(conversation_id=conversation_id)
        if memory is None:
            raise NotFoundException("Short term memory does not exist")
        self.short_term_memory_repository.delete_short_term_memory(memory=memory)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise