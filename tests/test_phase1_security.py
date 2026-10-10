import json
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from exceptions.application import NotFoundException
from graph.nodes import loader
from services.conversation_service import ConversationService


# ---------------------------------------------------------
# Existing unit tests
# ---------------------------------------------------------

def test_user_cannot_access_another_users_conversation(monkeypatch):
    """An unowned conversation should be treated as not found."""
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
        character_id=character_id,
        last_seq=0,
    )

    character_summary_repository = MagicMock()
    character_summary_repository.get_by_character_id.return_value = None

    stm_repository = MagicMock()
    stm_repository.get_memory_by_conversation_id.return_value = None

    ltm_repository = MagicMock()
    ltm_repository.get_memory_by_conversation_id.return_value = None

    message_repository = MagicMock()
    message_repository.get_recent.return_value = []

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
    """Memory lookups must use the requested conversation ID."""
    user_id = uuid4()
    character_id = uuid4()
    conversation_a_id = uuid4()
    conversation_b_id = uuid4()

    conversation_repository = MagicMock()
    conversation_repository.get_by_id.return_value = SimpleNamespace(
        character_id=character_id,
        last_seq=0,
    )

    character_summary_repository = MagicMock()
    character_summary_repository.get_by_character_id.return_value = None

    existing_memory_a = SimpleNamespace(
        content={"private": "conversation A"}
    )

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
    message_repository.get_recent.return_value = []

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


# ---------------------------------------------------------
# Integration-test helpers
# Uses the real API and the configured test database.
# ---------------------------------------------------------

def _create_user_and_login(client, email: str) -> dict:
    signup = client.post(
        "/users/",
        json={
            "email": email,
            "password": "StrongPassword123!",
        },
    )
    assert signup.status_code == 200, signup.text

    login = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "StrongPassword123!",
        },
    )
    assert login.status_code == 200, login.text

    token = login.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


def _create_character_and_conversation(client, headers: dict) -> str:
    character = client.post(
        "/characters/",
        headers=headers,
        json={
            "name": "Isolation Test Character",
            "avatar_url": None,
        },
    )
    assert character.status_code == 200, character.text

    character_id = character.json()["character_id"]

    conversation = client.post(
        "/conversations/",
        headers=headers,
        json={"character_id": character_id},
    )
    assert conversation.status_code == 200, conversation.text

    return conversation.json()["conversation_id"]


# ---------------------------------------------------------
# Real API isolation tests
# ---------------------------------------------------------

def test_user_b_cannot_access_user_a_conversation_resources(client):
    """User B must not access User A's conversation or memory endpoints."""
    headers_a = _create_user_and_login(
        client, "isolation-a@example.com"
    )
    headers_b = _create_user_and_login(
        client, "isolation-b@example.com"
    )

    conversation_id = _create_character_and_conversation(
        client, headers_a
    )

    response = client.get(
        f"/conversations/{conversation_id}",
        headers=headers_b,
    )
    assert response.status_code == 404, response.text

    response = client.get(
        f"/conversations/{conversation_id}/messages/",
        headers=headers_b,
    )
    assert response.status_code == 404, response.text

    response = client.get(
        f"/conversations/{conversation_id}/short-term-memory/",
        headers=headers_b,
    )
    assert response.status_code == 404, response.text

    response = client.get(
        f"/conversations/{conversation_id}/long-term-memory/",
        headers=headers_b,
    )
    assert response.status_code == 404, response.text


def test_user_b_chat_cannot_access_user_a_conversation(client):
    """Cross-user chat requests must return HTTP 404 before streaming."""
    headers_a = _create_user_and_login(
        client, "chat-isolation-a@example.com"
    )
    headers_b = _create_user_and_login(
        client, "chat-isolation-b@example.com"
    )

    conversation_id = _create_character_and_conversation(
        client, headers_a
    )

    response = client.post(
        f"/conversations/{conversation_id}/chat",
        headers=headers_b,
        json={"query": "Read the private conversation."},
    )

    assert response.status_code == 404, response.text
    assert not response.headers.get("content-type", "").startswith(
        "text/event-stream"
    )


def test_same_character_new_conversation_has_no_inherited_memory(client):
    """Separate conversations with one character must start with empty memory."""
    headers = _create_user_and_login(
        client, "memory-isolation@example.com"
    )

    character = client.post(
        "/characters/",
        headers=headers,
        json={
            "name": "Shared Character",
            "avatar_url": None,
        },
    )
    assert character.status_code == 200, character.text

    character_id = character.json()["character_id"]
    conversation_ids = []

    for _ in range(2):
        response = client.post(
            "/conversations/",
            headers=headers,
            json={"character_id": character_id},
        )
        assert response.status_code == 200, response.text
        conversation_ids.append(
            response.json()["conversation_id"]
        )

    assert conversation_ids[0] != conversation_ids[1]

    for conversation_id in conversation_ids:
        stm = client.get(
            f"/conversations/{conversation_id}/short-term-memory/",
            headers=headers,
        )
        ltm = client.get(
            f"/conversations/{conversation_id}/long-term-memory/",
            headers=headers,
        )

        assert stm.status_code == 404, stm.text
        assert ltm.status_code == 404, ltm.text