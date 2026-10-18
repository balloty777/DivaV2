from uuid import UUID
from sqlalchemy.orm import Session
from models.character import Character
from repositories.character_repository import CharacterRepository
from repositories.character_summary_repository import CharacterSummaryRepository
from repositories.user_repository import UserRepository
from exceptions.application import NotFoundException,ForbiddenException
from character.character_summary import create_character,StoredCharacterSummary


class CharacterService:
    def __init__(self, db: Session):
        self.db = db
        self.character_repository = CharacterRepository(db)
        self.character_summary_repository = CharacterSummaryRepository(db)
        self.user_repository = UserRepository(db)
    def create_character(self,creator_id: UUID,name: str,avatar_url: str | None = None) -> Character:
        user = self.user_repository.get_by_id(creator_id)
        if user is None:
            raise NotFoundException("User does not exist")

        # Characters are public as soon as they're created - no separate publish step.
        character = self.character_repository.create_character(
            creator_id=creator_id,name=name,status="active",avatar_url=avatar_url,
        )
        try:
            self.db.commit()
            self.db.refresh(character)
            return character
        except Exception:
            self.db.rollback()
            raise
    def create_character_from_summary(self,creator_id: UUID,name: str,summary: str,avatar_url: str | None = None) -> Character:
        user = self.user_repository.get_by_id(creator_id)
        if user is None:
            raise NotFoundException("User does not exist")
        structured_summary = create_character(f"Character name: {name}\n\nCharacter description:\n{summary}")
        if not structured_summary.characters:
            raise ValueError("The character summary could not be created")
        profile = structured_summary.characters[0].model_copy(update={"name": name})
        stored_profile=StoredCharacterSummary.model_validate(profile.model_dump())
        content = stored_profile.model_dump(mode="json")
        character = self.character_repository.create_character(creator_id=creator_id,name=name,status="active",avatar_url=avatar_url)
        self.db.flush()
        self.character_summary_repository.create_character_summary(character_id=character.character_id,content=content)

        try:
            self.db.commit()
            self.db.refresh(character)
            return character
        except Exception:
            self.db.rollback()
            raise
    def get_character(self,character_id: UUID) -> Character:
        character = self.character_repository.get_by_id(character_id=character_id)
        if character is None:
            raise NotFoundException("Character does not exist")
        return character
    def get_characters_by_creator(self,creator_id: UUID) -> list[Character]:
        user = self.user_repository.get_by_id(creator_id)
        if user is None:
            raise NotFoundException("User does not exist")
        return self.character_repository.get_by_creator(creator_id=creator_id)
    def get_public_characters(self) -> list[Character]:
        return self.character_repository.get_public_characters()
    def update_character(self,creator_id:UUID,character_id: UUID,name: str,avatar_url: str | None = None) -> Character:
        character = self.character_repository.get_by_id(character_id=character_id)
        if character is None:
            raise NotFoundException("Character does not exist")
        if creator_id!=character.creator_id:
            raise ForbiddenException("Not authorised")
        character = self.character_repository.update_character(character=character,name=name,avatar_url=avatar_url)
        try:
            self.db.commit()
            self.db.refresh(character)
            return character
        except Exception:
            self.db.rollback()
            raise
    def delete_character(self,creator_id:UUID,character_id: UUID) -> None:
        character = self.character_repository.get_by_id(character_id=character_id)
        if character is None:
            raise NotFoundException("Character does not exist")
        if creator_id!=character.creator_id:
            raise ForbiddenException("Not authorised")
        self.character_repository.delete_character(character=character)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise