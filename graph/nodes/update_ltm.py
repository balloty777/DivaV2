import logging
from langchain_core.runnables import RunnableConfig
from exceptions.application import NotFoundException
from graph.state import State
from memory.long_term_memory import LongTermMemory,create_long_term_memory
from repositories.conversation_repository import ConversationRepository
from repositories.long_term_memory_repository import LongTermMemoryRepository

LONG_TERM_MEMORY_INTERVAL = 20

logger = logging.getLogger(__name__)

def update_long_term_memory(state: State, config: RunnableConfig) -> dict:
    messages = state.get("messages", [])
    if not messages or len(messages) % LONG_TERM_MEMORY_INTERVAL != 0:
        return {}
    configurable = config.get("configurable", {})
    db = configurable.get("db")
    current_user_id = configurable.get("current_user_id")
    if db is None or current_user_id is None:
        raise RuntimeError("Graph config must include both 'db' and 'current_user_id'.")
    conversation_id = state["conversation_id"]
    conversation = ConversationRepository(db).get_by_id(user_id=current_user_id,conversation_id=conversation_id)
    if conversation is None:
        raise NotFoundException("Conversation does not exist")
    repository = LongTermMemoryRepository(db)
    memory_row = repository.get_memory_by_conversation_id(conversation_id)
    previous_memory = (LongTermMemory.model_validate(memory_row.content)if memory_row is not None else None)
    try:
        new_memory = create_long_term_memory(messages[-60:], previous_memory)
    except Exception:
        logger.exception("Long-term memory update failed for conversation %s",conversation_id)
        return {"long_term_memory": previous_memory} if previous_memory else {}
    content = new_memory.model_dump(mode="json")
    if memory_row is None:
        repository.create_long_term_memory(conversation_id, content)
    else:
        repository.update_long_term_memory(memory_row, content)
    db.flush()
    return {"long_term_memory": new_memory}