from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from exceptions.application import NotFoundException, ConflictException
from database.db import SessionLocal
from database.unit_of_work import UnitOfWork
from graph.nodes.loader import _to_characters
from graph.state import State
from memory.long_term_memory import LongTermMemory
from memory.short_term_memory import ShortTermMemory
from repositories.character_summary_repository import CharacterSummaryRepository
from repositories.conversation_repository import ConversationRepository
from repositories.long_term_memory_repository import LongTermMemoryRepository
from repositories.message_repository import MessageRepository
from repositories.short_term_memory_repository import ShortTermMemoryRepository
from repositories.conversation_character_summary_repository import ConversationCharacterSummaryRepository
from schemas.conversation_character_summary import ConversationCharacterState


def prepare_chat(state: State, config: RunnableConfig) -> dict:
    configurable = config.get("configurable", {})
    current_user_id = configurable.get("current_user_id")
    conversation_id = state["conversation_id"]

    if current_user_id is None:
        raise ConflictException("Graph config must include 'current_user_id'.")

    with SessionLocal() as db:
        with UnitOfWork(db):
            conversation = ConversationRepository(db).get_by_id(user_id=current_user_id,conversation_id=conversation_id)
            if conversation is None:
                raise NotFoundException("Conversation does not exist")
            character_summary_content = conversation.character_summary_snapshot
            if character_summary_content is None:
                character_summary_row = (CharacterSummaryRepository(db).get_by_character_id(conversation.character_id))
                character_summary_content = (character_summary_row.content if character_summary_row is not None else None)
            stm_row = ShortTermMemoryRepository(db).get_memory_by_conversation_id(conversation_id)
            ltm_row = LongTermMemoryRepository(db).get_memory_by_conversation_id(conversation_id)
            character_state_row = (ConversationCharacterSummaryRepository(db).get_by_conversation_id(conversation_id))
            character_state = (ConversationCharacterState.model_validate(character_state_row.content)if character_state_row is not None else None)
            message_rows = MessageRepository(db).get_recent(conversation_id=conversation_id,limit=20)
            context = {
                "messages": [
                    HumanMessage(content=message.content)
                    if message.role == "user"
                    else AIMessage(content=message.content)
                    for message in message_rows
                ],
                "last_seq": conversation.last_seq,
                "character_summary": (_to_characters(character_summary_content)if character_summary_content is not None else None),
                "character_state": character_state,
                "short_term_memory": (ShortTermMemory.model_validate(stm_row.content)if stm_row is not None else None),
                "long_term_memory": (LongTermMemory.model_validate(ltm_row.content)if ltm_row is not None else None)}
            MessageRepository(db).store_message(conversation_id=conversation_id,role="user",content=state["query"])
    return context