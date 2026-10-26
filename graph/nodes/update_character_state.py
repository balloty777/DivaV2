import logging
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from database.db import SessionLocal
from database.unit_of_work import UnitOfWork
from exceptions.application import ConflictException, NotFoundException
from graph.nodes.chat import get_model
from graph.state import State
from repositories.conversation_character_summary_repository import ConversationCharacterSummaryRepository
from repositories.conversation_repository import ConversationRepository
from schemas.conversation_character_summary import ConversationCharacterState

logger = logging.getLogger(__name__)
RELATIONSHIP_STAGES = ("new","acquaintance","familiar","close","intimate")

MAX_TRUST_CHANGE = 0.1
MAX_FAMILIARITY_CHANGE = 0.1

def _limit_change(current: float, proposed: float, maximum: float) -> float:
    return max(current - maximum, min(current + maximum, proposed))

def _limit_relationship_stage(current: str, proposed: str) -> str:
    current_index = RELATIONSHIP_STAGES.index(current)
    proposed_index = RELATIONSHIP_STAGES.index(proposed)
    if proposed_index > current_index:
        return RELATIONSHIP_STAGES[min(current_index + 1, proposed_index)]
    if proposed_index < current_index:
        return RELATIONSHIP_STAGES[max(current_index - 1, proposed_index)]
    return current

def update_character_state(state: State, config: RunnableConfig) -> dict:
    configurable = config.get("configurable", {})
    current_user_id = configurable.get("current_user_id")
    conversation_id = state["conversation_id"]
    previous_state = state.get("character_state")
    response = state.get("response")
    query = state.get("query")
    if current_user_id is None:
        raise ConflictException("Missing current user ID.")
    if previous_state is None or not query or not response:
        return {}
    expected_content = previous_state.model_dump(mode="json")
    try:
        proposed_state = get_model().with_structured_output(ConversationCharacterState).invoke(
            [
                SystemMessage(
                    content=(
                        "You update private roleplay relationship state for one "
                        "conversation. Return a complete state object. Base every "
                        "change on the current state and the latest exchange. "
                        "Keep mood concise. Change trust and familiarity gradually. "
                        "Do not infer consent, personal feelings, or intimacy from "
                        "ambiguous messages. Do not make large relationship jumps. "
                        "If the exchange provides no meaningful evidence for a "
                        "change, preserve the existing values."
                    )),
                HumanMessage(
                    content=(
                        f"Current state:\n{previous_state.model_dump_json()}\n\n"
                        f"User message:\n{query}\n\n"
                        f"Assistant reply:\n{response}"
                    ))])
        if not isinstance(proposed_state, ConversationCharacterState):
            proposed_state = ConversationCharacterState.model_validate(proposed_state)
        safe_state = proposed_state.model_copy(
            update={
                "trust": _limit_change(previous_state.trust,proposed_state.trust,MAX_TRUST_CHANGE),
                "familiarity": _limit_change(previous_state.familiarity,proposed_state.familiarity,MAX_FAMILIARITY_CHANGE),
                "relationship_stage": _limit_relationship_stage(previous_state.relationship_stage,proposed_state.relationship_stage)})
    except Exception:
        logger.exception("Character-state proposal failed for conversation %s",conversation_id)
        return {}
    try:
        with SessionLocal() as db:
            with UnitOfWork(db):
                conversation = ConversationRepository(db).get_by_id(user_id=current_user_id,conversation_id=conversation_id)
                if conversation is None:
                    raise NotFoundException("Conversation not found.")
                repository = ConversationCharacterSummaryRepository(db)
                current_row = repository.get_by_conversation_id_for_update(conversation_id)
                if current_row is None:
                    logger.warning("Character state is missing for conversation %s",conversation_id)
                    return {}
                current_content = ConversationCharacterState.model_validate(current_row.content).model_dump(mode="json")
                if current_content != expected_content:
                    logger.info("Skipping stale character-state update for conversation %s",conversation_id)
                    return {}
                repository.update_conversation_character_summary(summary=current_row,content=safe_state.model_dump(mode="json"))
                db.flush()
        return {"character_state": safe_state}
    except (NotFoundException, ConflictException):
        raise
    except Exception:
        logger.exception("Character-state persistence failed for conversation %s",conversation_id)
        return {}
