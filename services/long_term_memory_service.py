from uuid import UUID
from sqlalchemy.orm import Session
from repositories.long_term_memory_repository import LongTermMemoryRepository
from models.long_term_memory import LongTermMemory
from repositories.conversation_repository import ConversationRepository
from exceptions.application import NotFoundException, ConflictException

class LongTermMemoryService:
    def __init__(self, db: Session):
        self.db = db
        self.long_term_memory_repository = LongTermMemoryRepository(db)
        self.conversation_repository = ConversationRepository(db)
    def create_long_term_memory(self,user_id: UUID,conversation_id: UUID,content: dict) -> LongTermMemory:
        conversation = self.conversation_repository.get_by_id(user_id=user_id,conversation_id=conversation_id)
        if conversation is None:
            raise NotFoundException("Conversation does not exist")
        memory = self.long_term_memory_repository.get_memory_by_conversation_id(conversation_id=conversation_id)
        if memory is not None:
            raise ConflictException("Memory for this conversation already exist")
        ltm = self.long_term_memory_repository.create_long_term_memory(conversation_id=conversation_id,content=content)
        try:
            self.db.commit()
            self.db.refresh(ltm)
            return ltm
        except Exception:
            self.db.rollback()
            raise
    def get_long_term_memory(self,user_id: UUID,conversation_id: UUID) -> LongTermMemory:
        conversation = self.conversation_repository.get_by_id(user_id=user_id,conversation_id=conversation_id)
        if conversation is None:
            raise NotFoundException("Conversation does not exist")
        memory = self.long_term_memory_repository.get_memory_by_conversation_id(conversation_id=conversation_id)
        if memory is None:
            raise NotFoundException("Long term memory does not exist")
        return memory
    def update_long_term_memory(self,user_id: UUID,conversation_id: UUID,content: dict) -> LongTermMemory:
        conversation = self.conversation_repository.get_by_id(user_id=user_id,conversation_id=conversation_id)
        if conversation is None:
            raise NotFoundException("Conversation does not exist")
        memory = self.long_term_memory_repository.get_memory_by_conversation_id(conversation_id=conversation_id)
        if memory is None:
            raise NotFoundException("Long term memory does not exist")
        memory = self.long_term_memory_repository.update_long_term_memory(memory=memory,content=content)
        try:
            self.db.commit()
            self.db.refresh(memory)
            return memory
        except Exception:
            self.db.rollback()
            raise
    def delete_long_term_memory(self,user_id: UUID,conversation_id: UUID) -> None:
        conversation = self.conversation_repository.get_by_id(user_id=user_id,conversation_id=conversation_id)
        if conversation is None:
            raise NotFoundException("Conversation does not exist")
        memory = self.long_term_memory_repository.get_memory_by_conversation_id(conversation_id=conversation_id)
        if memory is None:
            raise NotFoundException("Long term memory does not exist")
        self.long_term_memory_repository.delete_long_term_memory(memory=memory)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise