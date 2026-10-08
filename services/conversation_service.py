from uuid import UUID
from sqlalchemy.orm import Session
from models.conversation import Conversation
from repositories.conversation_repository import ConversationRepository
from repositories.user_repository import UserRepository
from repositories.character_repository import CharacterRepository
from exceptions.application import NotFoundException,ForbiddenException


class ConversationService:
    def __init__(self, db: Session):
        self.db = db
        self.conversation_repository = ConversationRepository(db)
        self.user_repository = UserRepository(db)
        self.character_repository = CharacterRepository(db)
    def create_conversation(self,current_user_id:UUID,character_id: UUID) -> Conversation:
        user = self.user_repository.get_by_id(current_user_id)

        if user is None:
            raise NotFoundException("User does not exist")
        character = self.character_repository.get_by_id(character_id=character_id)
        if character is None:
            raise NotFoundException("Character does not exist")
        conversation = self.conversation_repository.create_conversation(
            user_id=current_user_id,character_id=character_id)
        try:
            self.db.commit()
            self.db.refresh(conversation)
            return conversation
        except Exception:
            self.db.rollback()
            raise
    def delete_conversation(self,user_id:UUID,conversation_id: UUID) -> None:
        conversation = self.conversation_repository.get_by_id(user_id=user_id,conversation_id=conversation_id)
        if conversation is None:
            raise NotFoundException("Conversation does not exist")
        if user_id!=conversation.user_id:
            raise ForbiddenException("Not Authorised")
        self.conversation_repository.delete_conversation(conversation)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
    def get_conversation(self,current_user_id:UUID,conversation_id: UUID) -> Conversation:
        conversation = self.conversation_repository.get_by_id(conversation_id=conversation_id)
        if conversation is None:
            raise NotFoundException("Conversation does not exist")
        if current_user_id!=conversation.user_id:
            raise ForbiddenException("Not Authorised")
        return conversation
    def get_conversations(self, current_user_id: UUID) -> list[Conversation]:
        return self.conversation_repository.get_by_user_id(current_user_id)
