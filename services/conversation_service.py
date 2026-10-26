from uuid import UUID
from sqlalchemy.orm import Session
from database.unit_of_work import UnitOfWork
from models.conversation import Conversation
from repositories.conversation_repository import ConversationRepository
from repositories.user_repository import UserRepository
from repositories.character_repository import CharacterRepository
from repositories.character_summary_repository import CharacterSummaryRepository
from exceptions.application import NotFoundException
from repositories.conversation_character_summary_repository import ConversationCharacterSummaryRepository
from schemas.conversation_character_summary import ConversationCharacterState

class ConversationService:
    def __init__(self, db: Session):
        self.db = db
        self.conversation_repository = ConversationRepository(db)
        self.user_repository = UserRepository(db)
        self.character_repository = CharacterRepository(db)

    def create_conversation(self,current_user_id: UUID,character_id: UUID) -> Conversation:
        user = self.user_repository.get_by_id(current_user_id)
        if user is None:
            raise NotFoundException("User does not exist")
        if not self.character_repository.is_available_to_user(character_id=character_id,user_id=current_user_id):
            raise NotFoundException("Character does not exist or is unavailable")
        character = self.character_repository.get_by_id(character_id=character_id)
        if character is None:
            raise NotFoundException("Character does not exist or is unavailable")
        with UnitOfWork(self.db):
            summary = CharacterSummaryRepository(self.db).get_by_character_id(character_id=character_id)
            conversation = self.conversation_repository.create_conversation(user_id=current_user_id,character_id=character_id)
            conversation.character_version = character.version
            conversation.character_summary_snapshot = (dict(summary.content) if summary is not None else None)
            self.db.flush()
            initial_state = ConversationCharacterState().model_dump()
            ConversationCharacterSummaryRepository(self.db).create_conversation_character_summary(conversation_id=conversation.conversation_id,content=initial_state)

            self.db.flush()
            self.db.refresh(conversation)

        return conversation

    def delete_conversation(self,user_id: UUID,conversation_id: UUID) -> None:
        conversation = self.conversation_repository.get_by_id(user_id=user_id,conversation_id=conversation_id)
        if conversation is None:
            raise NotFoundException("Conversation does not exist")
        with UnitOfWork(self.db):
            self.conversation_repository.delete_conversation(conversation)
    def get_conversation(self,current_user_id: UUID,conversation_id: UUID) -> Conversation:
        conversation = self.conversation_repository.get_by_id(user_id=current_user_id,conversation_id=conversation_id)
        if conversation is None:
            raise NotFoundException("Conversation does not exist")
        return conversation
    def get_conversations(self,current_user_id: UUID) -> list[Conversation]:
        return self.conversation_repository.get_by_user_id(current_user_id)