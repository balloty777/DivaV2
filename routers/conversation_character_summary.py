from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from auth.dependencies import get_current_user
from database.dependencies import get_db
from models.user import User
from services.conversation_character_summary_service import ConversationCharacterSummaryService


router = APIRouter(prefix="/conversations/{conversation_id}/character-summary",tags=["Conversation Character Summary"])

@router.get("/")
def get_conversation_character_summary(conversation_id: UUID,current_user: User = Depends(get_current_user),db: Session = Depends(get_db)):
    service = ConversationCharacterSummaryService(db)
    return service.get_conversation_character_summary(user_id=current_user.user_id,conversation_id=conversation_id)