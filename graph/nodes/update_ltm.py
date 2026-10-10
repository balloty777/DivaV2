import logging
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from exceptions.application import NotFoundException, ConflictException
from graph.state import State
from memory.long_term_memory import LongTermMemory,create_long_term_memory
from repositories.conversation_repository import ConversationRepository
from repositories.long_term_memory_repository import LongTermMemoryRepository
from repositories.message_repository import MessageRepository

LONG_TERM_MEMORY_INTERVAL = 20
logger = logging.getLogger(__name__)

def update_long_term_memory(state: State,config: RunnableConfig) -> dict:
    configurable = config.get("configurable", {})
    db = configurable.get("db")
    current_user_id = configurable.get("current_user_id")
    if db is None or current_user_id is None:
        raise ConflictException("Graph config must include both 'db' and 'current_user_id'.")
    conversation_id = state["conversation_id"]
    conversation = ConversationRepository(db).get_by_id(user_id=current_user_id,conversation_id=conversation_id)
    if conversation is None:
        raise NotFoundException("Conversation does not exist")
    current_seq = conversation.last_seq
    last_processed_seq = conversation.last_ltm_seq
    if current_seq - last_processed_seq < LONG_TERM_MEMORY_INTERVAL:
        return {}
    message_rows = MessageRepository(db).get_recent(conversation_id=conversation_id,limit=60)
    messages = [
        HumanMessage(content=message.content)
        if message.role == "user"
        else AIMessage(content=message.content)
        for message in message_rows
    ]
    if not messages:
        return {}
    repository = LongTermMemoryRepository(db)
    memory_row = repository.get_memory_by_conversation_id(conversation_id)
    previous_memory = (LongTermMemory.model_validate(memory_row.content)if memory_row is not None else None)
    try:
        new_memory = create_long_term_memory(messages, previous_memory)
    except Exception:
        logger.exception("Long-term memory update failed for conversation %s",conversation_id)
        return ({"long_term_memory": previous_memory}if previous_memory is not None else {})
    content = new_memory.model_dump(mode="json")
    if memory_row is None:
        repository.create_long_term_memory(conversation_id, content)
    else:
        repository.update_long_term_memory(memory_row, content)
    conversation.last_ltm_seq = current_seq
    db.flush()
    return {"long_term_memory": new_memory}
