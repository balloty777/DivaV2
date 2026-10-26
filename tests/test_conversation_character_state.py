import pytest
from pydantic import ValidationError
from uuid import UUID,uuid4
from schemas.conversation_character_summary import ConversationCharacterState
from models.user import User
from models.character import Character
from models.conversation import Conversation
from services.conversation_service import ConversationService
from contextlib import contextmanager
from types import SimpleNamespace

from graph.nodes import update_character_state as state_node


class FakeCharacterStateModel:
    """Fake LLM model that returns a predetermined character state."""

    def __init__(self, proposed_state=None, error=None):
        self.proposed_state = proposed_state
        self.error = error

    def with_structured_output(self, schema):
        assert schema is ConversationCharacterState
        return self

    def invoke(self, messages):
        if self.error is not None:
            raise self.error

        return self.proposed_state


class FakeDB:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def flush(self):
        pass


class FakeUnitOfWork:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def configure_state_update_mocks(
    monkeypatch,
    *,
    previous_state,
    proposed_state,
    stored_state=None,
    conversation_exists=True,
    llm_error=None,
):
    """Configure the database and model dependencies for state-update tests."""

    conversation_id = uuid4()
    user_id = uuid4()

    if stored_state is None:
        stored_state = previous_state.model_dump(mode="json")

    row = SimpleNamespace(
        conversation_id=conversation_id,
        content=dict(stored_state),
    )

    persisted = {}

    monkeypatch.setattr(state_node, "SessionLocal", FakeDB)
    monkeypatch.setattr(state_node, "UnitOfWork", FakeUnitOfWork)

    monkeypatch.setattr(
        state_node,
        "get_model",
        lambda: FakeCharacterStateModel(
            proposed_state=proposed_state,
            error=llm_error,
        ),
    )

    class FakeConversationRepository:
        def __init__(self, db):
            pass

        def get_by_id(self, *, user_id, conversation_id):
            if conversation_exists:
                return SimpleNamespace(conversation_id=conversation_id)
            return None

    class FakeCharacterStateRepository:
        def __init__(self, db):
            pass

        def get_by_conversation_id_for_update(self, requested_id):
            assert requested_id == conversation_id
            return row

        def update_conversation_character_summary(self, *, summary, content):
            persisted["content"] = dict(content)
            summary.content = dict(content)

    monkeypatch.setattr(
        state_node,
        "ConversationRepository",
        FakeConversationRepository,
    )

    monkeypatch.setattr(
        state_node,
        "ConversationCharacterSummaryRepository",
        FakeCharacterStateRepository,
    )

    state = {
        "conversation_id": conversation_id,
        "character_state": previous_state,
        "query": "I enjoyed talking with you.",
        "response": "I'm glad we could talk.",
    }

    config = {
        "configurable": {
            "current_user_id": user_id,
        }
    }

    return state, config, persisted


def test_character_state_update_limits_trust_and_familiarity(monkeypatch):
    previous_state = ConversationCharacterState(
        mood="calm",
        trust=0.5,
        familiarity=0.4,
        relationship_stage="familiar",
    )

    proposed_state = ConversationCharacterState(
        mood="happy",
        trust=1.0,
        familiarity=0.0,
        relationship_stage="familiar",
    )

    state, config, persisted = configure_state_update_mocks(
        monkeypatch,
        previous_state=previous_state,
        proposed_state=proposed_state,
    )

    result = state_node.update_character_state(state, config)

    updated = result["character_state"]

    assert updated.mood == "happy"
    assert updated.trust == pytest.approx(0.6)
    assert updated.familiarity == pytest.approx(0.3)

    assert persisted["content"]["trust"] == pytest.approx(0.6)
    assert persisted["content"]["familiarity"] == pytest.approx(0.3)


def test_character_state_update_limits_relationship_stage_progression(
    monkeypatch,
):
    previous_state = ConversationCharacterState(
        trust=0.5,
        familiarity=0.5,
        relationship_stage="new",
    )

    proposed_state = ConversationCharacterState(
        trust=0.5,
        familiarity=0.5,
        relationship_stage="intimate",
    )

    state, config, persisted = configure_state_update_mocks(
        monkeypatch,
        previous_state=previous_state,
        proposed_state=proposed_state,
    )

    result = state_node.update_character_state(state, config)

    assert result["character_state"].relationship_stage == "acquaintance"
    assert persisted["content"]["relationship_stage"] == "acquaintance"


def test_character_state_update_can_decrease_relationship_stage(
    monkeypatch,
):
    previous_state = ConversationCharacterState(
        trust=0.5,
        familiarity=0.5,
        relationship_stage="close",
    )

    proposed_state = ConversationCharacterState(
        trust=0.5,
        familiarity=0.5,
        relationship_stage="new",
    )

    state, config, _ = configure_state_update_mocks(
        monkeypatch,
        previous_state=previous_state,
        proposed_state=proposed_state,
    )

    result = state_node.update_character_state(state, config)

    assert result["character_state"].relationship_stage == "familiar"


def test_character_state_update_skips_stale_proposal(monkeypatch):
    previous_state = ConversationCharacterState(
        trust=0.3,
        familiarity=0.2,
        relationship_stage="new",
    )

    proposed_state = ConversationCharacterState(
        trust=0.4,
        familiarity=0.3,
        relationship_stage="acquaintance",
    )

    newer_stored_state = {
        "mood": "excited",
        "trust": 0.7,
        "familiarity": 0.6,
        "relationship_stage": "familiar",
    }

    state, config, persisted = configure_state_update_mocks(
        monkeypatch,
        previous_state=previous_state,
        proposed_state=proposed_state,
        stored_state=newer_stored_state,
    )

    result = state_node.update_character_state(state, config)

    assert result == {}
    assert persisted == {}


def test_character_state_update_handles_llm_failure(monkeypatch):
    previous_state = ConversationCharacterState(
        trust=0.2,
        familiarity=0.1,
        relationship_stage="new",
    )

    state, config, persisted = configure_state_update_mocks(
        monkeypatch,
        previous_state=previous_state,
        proposed_state=None,
        llm_error=RuntimeError("Simulated LLM failure"),
    )

    result = state_node.update_character_state(state, config)

    assert result == {}
    assert persisted == {}


def test_character_state_update_skips_when_state_is_missing(monkeypatch):
    previous_state = ConversationCharacterState()

    state, config, persisted = configure_state_update_mocks(
        monkeypatch,
        previous_state=previous_state,
        proposed_state=ConversationCharacterState(mood="curious"),
    )

    monkeypatch.setattr(
        state_node,
        "ConversationCharacterSummaryRepository",
        lambda db: SimpleNamespace(
            get_by_conversation_id_for_update=lambda conversation_id: None,
        ),
    )

    result = state_node.update_character_state(state, config)

    assert result == {}
    assert persisted == {}


def test_character_state_update_rejects_missing_user_id(monkeypatch):
    previous_state = ConversationCharacterState()

    state = {
        "conversation_id": uuid4(),
        "character_state": previous_state,
        "query": "Hello.",
        "response": "Hello!",
    }

    with pytest.raises(Exception) as exc_info:
        state_node.update_character_state(state, {"configurable": {}})

    assert "Missing current user ID" in str(exc_info.value)

def test_character_state_uses_defaults():
    state = ConversationCharacterState()

    assert state.mood == "calm"
    assert state.trust == 0.0
    assert state.familiarity == 0.0
    assert state.relationship_stage == "new"


def test_character_state_accepts_valid_values():
    state = ConversationCharacterState(
        mood="curious",
        trust=0.65,
        familiarity=0.4,
        relationship_stage="familiar",
    )

    assert state.trust == 0.65
    assert state.familiarity == 0.4
    assert state.relationship_stage == "familiar"


@pytest.mark.parametrize(
    "field,value",
    [
        ("trust", -0.1),
        ("trust", 1.1),
        ("familiarity", -0.1),
        ("familiarity", 1.1),
        ("relationship_stage", "unknown"),
    ],
)
def test_character_state_rejects_invalid_values(field, value):
    with pytest.raises(ValidationError):
        ConversationCharacterState(**{field: value})


def test_character_state_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        ConversationCharacterState(unexpected="value")
    
def test_create_conversation_initializes_private_character_state(db_session):
    from repositories.conversation_character_summary_repository import (
        ConversationCharacterSummaryRepository,
    )

    user_id = uuid4()
    character_id = uuid4()

    user = User(
        user_id=user_id,
        email="private-state-test@example.com",
        password_hash="test-password-hash",
    )

    character = Character(
        character_id=character_id,
        creator_id=user_id,
        name="Aria",
        status="active",
        version=1,
    )

    db_session.add_all([user, character])
    db_session.commit()

    service = ConversationService(db_session)

    conversation_a = service.create_conversation(
        current_user_id=user_id,
        character_id=character_id,
    )
    conversation_b = service.create_conversation(
        current_user_id=user_id,
        character_id=character_id,
    )

    repository = ConversationCharacterSummaryRepository(db_session)

    state_a = repository.get_by_conversation_id(
        conversation_a.conversation_id
    )
    state_b = repository.get_by_conversation_id(
        conversation_b.conversation_id
    )

    assert state_a is not None
    assert state_b is not None
    assert state_a.conversation_id != state_b.conversation_id

    assert state_a.content == {
        "mood": "calm",
        "trust": 0.0,
        "familiarity": 0.0,
        "relationship_stage": "new",
    }

    assert state_b.content == state_a.content

    state_a.content = {
        **state_a.content,
        "trust": 0.8,
        "familiarity": 0.7,
        "relationship_stage": "close",
    }
    db_session.commit()
    db_session.refresh(state_b)

    assert state_a.content["trust"] == 0.8
    assert state_b.content["trust"] == 0.0
    assert state_b.content["relationship_stage"] == "new"