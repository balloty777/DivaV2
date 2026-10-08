from uuid import UUID
from sqlalchemy.orm import Session
from repositories.message_repository import MessageRepository
from repositories.conversation_repository import ConversationRepository
from models.message import Message
from exceptions.application import NotFoundException
class MessageService:
    def __init__(self,db:Session):
        self.db=db
        self.message_repository=MessageRepository(db)
        self.conversation_repository=ConversationRepository(db)
    def store_message(self,user_id:UUID,conversation_id:UUID,content:str,role:str)->Message:
        conversation=self.conversation_repository.get_by_id(user_id=user_id,conversation_id=conversation_id)
        if conversation is None:
            raise NotFoundException("Conversation does not exist")
        if user_id!=conversation.user_id:
            raise ForbiddenException("Not Authorised")
        message=self.message_repository.store_message(conversation_id=conversation_id,content=content,role=role)
        try:
            self.db.commit()
            self.db.refresh(message)
            return message
        except Exception:
            self.db.rollback()
            raise
    def get_message_by_id(self,user_id:UUID,message_id:UUID)->Message:
        message=self.message_repository.get_message_by_id(message_id=message_id)
        if message is None:
            raise NotFoundException("Message does not exist")
        conversation=self.conversation_repository.get_by_id(user_id=user_id,conversation_id=message.conversation_id)
        if conversation is None:
            raise NotFoundException("Message does not exist")
        return message
    def get_message_by_conversation_id(self,user_id:UUID,conversation_id:UUID)->list[Message]:
        conversation=self.conversation_repository.get_by_id(user_id=user_id,conversation_id=conversation_id)
        if conversation is None:
            raise NotFoundException("Message does not exist")
        message=self.message_repository.get_message_by_conversation_id(conversation_id=conversation_id)
        return message
    def get_message_by_role(self,user_id:UUID,conversation_id:UUID,role:str)->list[Message]:
        message=self.message_repository.get_message_by_role(role=role,conversation_id=conversation_id)
        conversation=self.conversation_repository.get_by_id(user_id=user_id,conversation_id=conversation_id)
        if conversation is None:
            raise NotFoundException("Message does not exist")
        return message
    def delete_message(self,user_id:UUID,message_id:UUID)->None:
        message=self.message_repository.get_message_by_id(message_id=message_id)
        if message is None:
            raise NotFoundException("Message does not exist")
        conversation=self.conversation_repository.get_by_id(user_id=user_id,conversation_id=message.conversation_id)
        if conversation is None:
            raise NotFoundException("Message does not exist")
        
        self.message_repository.delete_message(message=message)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise