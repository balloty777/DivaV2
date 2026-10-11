from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from exceptions.application import NotFoundException, ConflictException
from database.db import SessionLocal
from database.unit_of_work import UnitOfWork
from graph.state import State
from repositories.conversation_repository import ConversationRepository
from repositories.message_repository import MessageRepository
from repositories.memory_job_repository import MemoryJobRepository

def save_assistant_message(state: State, config: RunnableConfig) -> dict:
    configurable = config.get("configurable", {})
    current_user_id = configurable.get("current_user_id")
    conversation_id = state["conversation_id"]
    response = state.get("response")
    if current_user_id is None:
        raise ConflictException("Missing current user ID.")
    if not response:
        raise ConflictException("Missing assistant response.")
    with SessionLocal() as db:
        with UnitOfWork(db):
            conversation = ConversationRepository(db).get_by_id(user_id=current_user_id,conversation_id=conversation_id)
            if conversation is None:
                raise NotFoundException("Conversation not found.")
            message = MessageRepository(db).store_message(conversation_id=conversation_id,role="assistant",content=response)
            MemoryJobRepository(db).create(conversation_id=conversation_id,through_seq=message.seq)
            db.flush()
            return {"messages": [*state.get("messages", []),AIMessage(content=response)],"last_seq": message.seq}   