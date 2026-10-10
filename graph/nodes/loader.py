from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from sqlalchemy.orm import Session
from character.character_summary import CharacterSummary, Characters
from exceptions.application import NotFoundException
from graph.state import State
from memory.long_term_memory import LongTermMemory
from memory.short_term_memory import ShortTermMemory
from repositories.character_summary_repository import CharacterSummaryRepository
from repositories.conversation_repository import ConversationRepository
from repositories.long_term_memory_repository import LongTermMemoryRepository
from repositories.message_repository import MessageRepository
from repositories.short_term_memory_repository import ShortTermMemoryRepository

def _get_runtime(config: RunnableConfig) -> tuple[Session, object]:
    configurable = config.get("configurable", {})
    db = configurable.get("db")
    current_user_id = configurable.get("current_user_id")
    if db is None or current_user_id is None:
        raise RuntimeError("Graph config must include both 'db' and 'current_user_id'.")
    return db, current_user_id


def _to_characters(content: dict) -> Characters:
    """
    Supports either of these PostgreSQL JSONB formats:

    {"characters": [{...}]}
    {...single character fields...}
    """
    if "characters" in content:
        return Characters.model_validate(content)

    return Characters(characters=[CharacterSummary.model_validate(content)])


def load_context(state: State, config: RunnableConfig) -> dict:
    db, current_user_id = _get_runtime(config)
    conversation_id = state["conversation_id"]
    message_repository=MessageRepository(db)
    conversation = ConversationRepository(db).get_by_id(
        user_id=current_user_id,
        conversation_id=conversation_id,
    )

    if conversation is None:
        raise NotFoundException("Conversation does not exist")

    character_summary_row = CharacterSummaryRepository(db).get_by_character_id(
        conversation.character_id
    )

    short_term_memory_row = (
        ShortTermMemoryRepository(db)
        .get_memory_by_conversation_id(conversation_id)
    )

    long_term_memory_row = (
        LongTermMemoryRepository(db)
        .get_memory_by_conversation_id(conversation_id)
    )

    message_rows = message_repository.get_recent(conversation_id=conversation_id,limit=20)

    messages = [
        HumanMessage(content=message.content)
        if message.role == "user"
        else AIMessage(content=message.content)
        for message in message_rows
    ]

    return {
        "messages": messages,
        "last_seq":conversation.last_seq,
        "character_summary": (
            _to_characters(character_summary_row.content)
            if character_summary_row is not None
            else None
        ),
        "short_term_memory": (
            ShortTermMemory.model_validate(short_term_memory_row.content)
            if short_term_memory_row is not None
            else None
        ),
        "long_term_memory": (
            LongTermMemory.model_validate(long_term_memory_row.content)
            if long_term_memory_row is not None
            else None
        ),
    }