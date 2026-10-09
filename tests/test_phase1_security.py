
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from exceptions.application import NotFoundException
from graph.nodes import loader
from services.conversation_service import ConversationService


def test_user_cannot_access_another_users_conversation(monkeypatch):
    """An unowned conversation should be treated as not found."""
    user_a_id = uuid4()
    user_b_id = uuid4()
    conversation_id = uuid4()

    repository = MagicMock()
    repository.get_by_id.return_value = None

    monkeypatch.setattr(
        "services.conversation_service.ConversationRepository",
        lambda db: repository,
    )

    service = ConversationService(db=MagicMock())

    with pytest.raises(NotFoundException):
        service.get_conversation(
            current_user_id=user_b_id,
            conversation_id=conversation_id,
        )

    repository.get_by_id.assert_called_once_with(
        user_id=user_b_id,
        conversation_id=conversation_id,
    )


def test_new_conversation_starts_without_existing_memory(monkeypatch):
    """A new conversation must not inherit STM or LTM from another conversation."""
    user_id = uuid4()
    character_id = uuid4()
    conversation_id = uuid4()

    conversation_repository = MagicMock()
    conversation_repository.get_by_id.return_value = SimpleNamespace(
        character_id=character_id
    )

    character_summary_repository = MagicMock()
    character_summary_repository.get_by_character_id.return_value = None

    stm_repository = MagicMock()
    stm_repository.get_memory_by_conversation_id.return_value = None

    ltm_repository = MagicMock()
    ltm_repository.get_memory_by_conversation_id.return_value = None

    message_repository = MagicMock()
    message_repository.get_message_by_conversation_id.return_value = []

    monkeypatch.setattr(
        loader,
        "ConversationRepository",
        lambda db: conversation_repository,
    )
    monkeypatch.setattr(
        loader,
        "CharacterSummaryRepository",
        lambda db: character_summary_repository,
    )
    monkeypatch.setattr(
        loader,
        "ShortTermMemoryRepository",
        lambda db: stm_repository,
    )
    monkeypatch.setattr(
        loader,
        "LongTermMemoryRepository",
        lambda db: ltm_repository,
    )
    monkeypatch.setattr(
        loader,
        "MessageRepository",
        lambda db: message_repository,
    )

    result = loader.load_context(
        {"conversation_id": conversation_id},
        {
            "configurable": {
                "db": MagicMock(),
                "current_user_id": user_id,
            }
        },
    )

    assert result["short_term_memory"] is None
    assert result["long_term_memory"] is None
    assert result["messages"] == []

    stm_repository.get_memory_by_conversation_id.assert_called_once_with(
        conversation_id
    )
    ltm_repository.get_memory_by_conversation_id.assert_called_once_with(
        conversation_id
    )


def test_memory_lookup_uses_the_requested_conversation_id(monkeypatch):
    """Memory from conversation A must not be loaded for conversation B."""
    user_id = uuid4()
    character_id = uuid4()
    conversation_a_id = uuid4()
    conversation_b_id = uuid4()

    conversation_repository = MagicMock()
    conversation_repository.get_by_id.return_value = SimpleNamespace(
        character_id=character_id
    )

    character_summary_repository = MagicMock()
    character_summary_repository.get_by_character_id.return_value = None

    # Simulate existing memory for A, but no memory for B.
    existing_memory_a = SimpleNamespace(content={"private": "conversation A"})
    stm_repository = MagicMock()
    stm_repository.get_memory_by_conversation_id.side_effect = (
        lambda conversation_id: (
            existing_memory_a
            if conversation_id == conversation_a_id
            else None
        )
    )

    ltm_repository = MagicMock()
    ltm_repository.get_memory_by_conversation_id.side_effect = (
        lambda conversation_id: (
            existing_memory_a
            if conversation_id == conversation_a_id
            else None
        )
    )

    message_repository = MagicMock()
    message_repository.get_message_by_conversation_id.return_value = []

    monkeypatch.setattr(
        loader,
        "ConversationRepository",
        lambda db: conversation_repository,
    )
    monkeypatch.setattr(
        loader,
        "CharacterSummaryRepository",
        lambda db: character_summary_repository,
    )
    monkeypatch.setattr(
        loader,
        "ShortTermMemoryRepository",
        lambda db: stm_repository,
    )
    monkeypatch.setattr(
        loader,
        "LongTermMemoryRepository",
        lambda db: ltm_repository,
    )
    monkeypatch.setattr(
        loader,
        "MessageRepository",
        lambda db: message_repository,
    )

    result = loader.load_context(
        {"conversation_id": conversation_b_id},
        {
            "configurable": {
                "db": MagicMock(),
                "current_user_id": user_id,
            }
        },
    )

    assert result["short_term_memory"] is None
    assert result["long_term_memory"] is None

    stm_repository.get_memory_by_conversation_id.assert_called_once_with(
        conversation_b_id
    )
    ltm_repository.get_memory_by_conversation_id.assert_called_once_with(
        conversation_b_id
    )
