import logging
from langchain_core.runnables import RunnableConfig
from exceptions.application import NotFoundException, ConflictException
from graph.state import State
from memory.short_term_memory import ShortTermMemory,create_short_term_memory
from repositories.conversation_repository import ConversationRepository
from repositories.short_term_memory_repository import ShortTermMemoryRepository

logger = logging.getLogger(__name__)
SHORT_TERM_MEMORY_INTERVAL = 4

def update_short_term_memory(state: State,config: RunnableConfig) -> dict:
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
    last_processed_seq = conversation.last_stm_seq
    if current_seq - last_processed_seq < SHORT_TERM_MEMORY_INTERVAL:
        return {}
    messages = state.get("messages", [])
    if not messages:
        return {}
    repository = ShortTermMemoryRepository(db)
    memory_row = repository.get_memory_by_conversation_id(conversation_id)
    previous_memory = (ShortTermMemory.model_validate(memory_row.content)if memory_row is not None else None)
    try:
        new_memory = create_short_term_memory(messages[-20:],previous_memory)
    except Exception:
        logger.exception("Short-term memory update failed for conversation %s",conversation_id)
        return ({"short_term_memory": previous_memory}if previous_memory is not None else {})
    content = new_memory.model_dump(mode="json")
    if memory_row is None:
        repository.create_short_term_memory(conversation_id, content)
    else:
        repository.update_short_term_memory(memory_row, content)
    conversation.last_stm_seq = current_seq
    db.flush()
    return {"short_term_memory": new_memory}