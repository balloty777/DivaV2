from uuid import UUID
from sqlalchemy import case, select,update
from sqlalchemy.orm import Session
from models.message import Message
from models.conversation import Conversation
from exceptions.application import NotFoundException,ConflictException
class MessageRepository:
    def __init__(self,db:Session):
        self.db=db
    def store_message(self,conversation_id:UUID,content:str,role:str)->Message:
        stmt=select(Conversation).where(Conversation.conversation_id==conversation_id).with_for_update()
        conversation=self.db.scalar(stmt)
        if conversation is None:
            raise NotFoundException("Conversation does not exist")
        conversation.last_seq+=1
        message=Message(conversation_id=conversation_id,seq=conversation.last_seq,content=content,role=role)
        self.db.add(message)
        return message
    def get_message_by_id(self,message_id:UUID)->Message|None:
        return self.db.get(Message,message_id)
    def get_message_by_conversation_id(self,conversation_id:UUID)->list[Message]:
        stmt=(select(Message).where(Message.conversation_id==conversation_id).order_by(Message.seq.asc()))
        return list(self.db.scalars(stmt).all())
    def get_recent(self,conversation_id:UUID,limit:int=20)->list[Message]:
        if limit<1:
            raise ConflictException("Limit must me at least 1")
        stmt=select(Message).where(Message.conversation_id==conversation_id).order_by(Message.seq.desc()).limit(limit)
        messages=list(self.db.scalar(stmt).all())
        messages.reverse()
        return messages
    def get_message_by_role(self,conversation_id:UUID,role:str)->list[Message]:
        stmt = (select(Message).where(Message.role==role, Message.conversation_id==conversation_id).order_by(Message.created_at.asc()))
        return list(self.db.scalars(stmt).all())
    def delete_message(self,message:Message)->None:
        self.db.delete(message)

