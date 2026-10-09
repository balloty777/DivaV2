from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from models.character import Character

class CharacterRepository:
    def __init__(self, db: Session):
        self.db = db
    def create_character(self,creator_id: UUID,name: str,status: str = "draft",avatar_url: str | None = None) -> Character:
        character = Character(creator_id=creator_id,name=name,status=status,avatar_url=avatar_url)
        self.db.add(character)
        return character
    def get_by_id(self,character_id: UUID) -> Character | None:
        stmt = select(Character).where(Character.character_id == character_id)
        return self.db.scalar(stmt)
    def is_available_to_user(self, character_id: UUID, user_id: UUID) -> bool:
        stmt = select(Character.character_id).where(Character.character_id == character_id,((Character.status == "active")| (Character.creator_id == user_id)))
        return self.db.scalar(stmt) is not None
    def get_by_creator(self,creator_id: UUID) -> list[Character]:
        stmt = (select(Character).where(Character.creator_id == creator_id).order_by(Character.created_at.desc()))
        return list(self.db.scalars(stmt).all())
    def get_public_characters(self) -> list[Character]:
        stmt = (
            select(Character)
            .where(Character.status == "active")
            .options(joinedload(Character.character_summary))
            .order_by(Character.created_at.desc())
        )
        return list(self.db.scalars(stmt).unique().all())
    def update_character(self,character: Character,name: str,avatar_url: str | None = None) -> Character:
        character.name = name
        if avatar_url is not None:
            character.avatar_url = avatar_url
        return character
    def delete_character(self,character: Character,) -> None:
        self.db.delete(character)