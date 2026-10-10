from uuid import UUID

from sqlalchemy.orm import Session

from models.character_summary import CharacterSummary
from repositories.character_repository import CharacterRepository
from repositories.character_summary_repository import CharacterSummaryRepository
from exceptions.application import NotFoundException,ForbiddenException



class CharacterSummaryService:
    def __init__(self, db: Session):
        self.db = db
        self.character_summary_repository = CharacterSummaryRepository(db)
        self.character_repository = CharacterRepository(db)
    def create_character_summary(self,user_id:UUID,character_id: UUID,content: dict) -> CharacterSummary:
        character = self.character_repository.get_by_id(character_id=character_id)
        if character is None:
            raise NotFoundException("Character does not exist")
        if user_id!=character.creator_id:
            raise ForbiddenException("Not authorised")
        character_summary = (self.character_summary_repository.create_character_summary(character_id=character_id,content=content))
        try:
            self.db.commit()
            self.db.refresh(character_summary)
            return character_summary
        except Exception:
            self.db.rollback()
            raise
    def get_character_summary(self,user_id: UUID,character_id: UUID) -> CharacterSummary:
        character = self.character_repository.get_by_id(character_id=character_id)
        if character is None:
            raise NotFoundException("Character does not exist")
        if not self.character_repository.is_available_to_user(character_id=character_id,user_id=user_id):
            raise NotFoundException("Character does not exist")
        character_summary = (self.character_summary_repository.get_by_character_id(character_id=character_id))
        if character_summary is None:
            raise NotFoundException("Character Summary does not exist")
        return character_summary
    def update_character_summary(self,user_id: UUID,character_id: UUID,content: dict) -> CharacterSummary:
        character = self.character_repository.get_by_id(character_id=character_id)
        if character is None:
            raise NotFoundException("Character does not exist")
        if user_id != character.creator_id:
            raise ForbiddenException("Not authorised")
        character_summary = (self.character_summary_repository.get_by_character_id(character_id=character_id))
        if character_summary is None:
            raise NotFoundException("Character Summary does not exist")
        character_summary = (self.character_summary_repository.update_character_summary(character_summary=character_summary,content=content))
        try:
            self.db.commit()
            self.db.refresh(character_summary)
            return character_summary
        except Exception:
            self.db.rollback()
            raise
    def delete_character_summary(self,user_id: UUID,character_id: UUID,) -> None:
        character = self.character_repository.get_by_id(character_id=character_id)
        if character is None:
            raise NotFoundException("Character does not exist")
        if user_id != character.creator_id:
            raise ForbiddenException("Not authorised")
        character_summary = (self.character_summary_repository.get_by_character_id(character_id=character_id))
        if character_summary is None:
            raise NotFoundException("Character Summary does not exist")
        self.character_summary_repository.delete_character_summary(character_summary=character_summary)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise