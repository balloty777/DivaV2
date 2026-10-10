from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from auth.dependencies import get_current_user
from database.dependencies import get_db
from models.user import User
from schemas.character_summary import CharacterSummaryCreate
from services.character_summary_service import CharacterSummaryService


router = APIRouter(prefix="/characters/{character_id}/character-summary",tags=["Character Summary"])

@router.post("/")
def create_character_summary(character_id: UUID,data: CharacterSummaryCreate,current_user: User = Depends(get_current_user),db: Session = Depends(get_db)):
    service = CharacterSummaryService(db)
    return service.create_character_summary(user_id=current_user.user_id,character_id=character_id,content=data.content)

@router.get("/")
def get_character_summary(character_id: UUID,current_user: User = Depends(get_current_user),db: Session = Depends(get_db)):
    service = CharacterSummaryService(db)
    return service.get_character_summary(user_id=current_user.user_id,character_id=character_id)

@router.put("/")
def update_character_summary(character_id: UUID,data: CharacterSummaryCreate,current_user: User = Depends(get_current_user),db: Session = Depends(get_db)):
    service = CharacterSummaryService(db)
    return service.update_character_summary(user_id=current_user.user_id,character_id=character_id,content=data.content)

@router.delete("/")
def delete_character_summary(character_id: UUID,current_user: User = Depends(get_current_user),db: Session = Depends(get_db)):
    service = CharacterSummaryService(db)
    service.delete_character_summary(user_id=current_user.user_id,character_id=character_id)
    return {"detail": "Character summary deleted successfully"}