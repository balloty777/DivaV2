from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from auth.dependencies import get_current_user
from database.dependencies import get_db
from models.user import User
from services.message_service import MessageService

router = APIRouter(prefix="/conversations/{conversation_id}/messages",tags=["Messages"])

@router.get("/{message_id}")
def get_message_by_id(message_id: UUID,current_user: User = Depends(get_current_user),db: Session = Depends(get_db)):
    service = MessageService(db)
    return service.get_message_by_id(user_id=current_user.user_id,message_id=message_id)

@router.get("/")
def get_messages_by_conversation_id(conversation_id: UUID,current_user: User = Depends(get_current_user),db: Session = Depends(get_db)):
    service = MessageService(db)
    return service.get_message_by_conversation_id(user_id=current_user.user_id,conversation_id=conversation_id)

@router.get("/role/{role}")
def get_messages_by_role(role: str,conversation_id: UUID,current_user: User = Depends(get_current_user),db: Session = Depends(get_db)):
    service = MessageService(db)
    return service.get_message_by_role(user_id=current_user.user_id,conversation_id=conversation_id,role=role)
