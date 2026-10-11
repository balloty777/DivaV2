import json
from uuid import UUID

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from sqlalchemy import select

from database.db import SessionLocal, engine
from models.memory_job import MemoryJob
from models.message import Message


def test_chat(client, monkeypatch):
    # Replace the real OpenRouter model with a deterministic fake.
    fake_model = FakeListChatModel(
        responses=["This is a test response."]
    )

    class ConnectionCheckingModel:
        def invoke(self, prompt, *args, **kwargs):
            assert engine.pool.checkedout() == 0, (
                "A database connection was checked out during LLM invocation."
            )
            return fake_model.invoke(prompt, *args, **kwargs)

    monkeypatch.setattr(
        "graph.nodes.chat.get_model",
        lambda: ConnectionCheckingModel(),
    )

    # Create the user.
    signup_response = client.post(
        "/users/",
        json={
            "email": "chat-test@example.com",
            "password": "StrongPassword123!",
        },
    )
    assert signup_response.status_code == 200

    # Log in.
    login_response = client.post(
        "/auth/login",
        json={
            "email": "chat-test@example.com",
            "password": "StrongPassword123!",
        },
    )
    assert login_response.status_code == 200

    headers = {
        "Authorization": f"Bearer {login_response.json()['access_token']}"
    }

    # Create a character.
    character_response = client.post(
        "/characters/",
        headers=headers,
        json={
            "name": "Chat Test Character",
            "avatar_url": None,
        },
    )
    assert character_response.status_code == 200
    character_id = character_response.json()["character_id"]

    # Create a conversation.
    conversation_response = client.post(
        "/conversations/",
        headers=headers,
        json={"character_id": character_id},
    )
    assert conversation_response.status_code == 200
    conversation_id = UUID(
        conversation_response.json()["conversation_id"]
    )

    # Send a chat request.
    chat_response = client.post(
        f"/conversations/{conversation_id}/chat",
        headers=headers,
        json={"query": "Hello!"},
    )

    assert chat_response.status_code == 200
    assert chat_response.headers["content-type"].startswith(
        "text/event-stream"
    )

    response_text = chat_response.text
    assert '"type": "token"' in response_text

    token_content = ""
    for line in response_text.splitlines():
        if line.startswith("data: "):
            event = json.loads(line[6:])
            if event.get("type") == "token":
                token_content += event["content"]

    assert token_content == "This is a test response."
    assert '"type": "done"' in response_text
    assert str(conversation_id) in response_text

    # Verify both messages were persisted.
    messages_response = client.get(
        f"/conversations/{conversation_id}/messages/",
        headers=headers,
    )
    assert messages_response.status_code == 200

    messages = messages_response.json()
    assert len(messages) == 2

    messages_by_seq = sorted(
        messages,
        key=lambda message: message["seq"],
    )

    assert messages_by_seq[0]["role"] == "user"
    assert messages_by_seq[0]["content"] == "Hello!"
    assert messages_by_seq[1]["role"] == "assistant"
    assert messages_by_seq[1]["content"] == "This is a test response."

    # Verify the pending memory job.
    with SessionLocal() as db:
        jobs = db.scalars(
            select(MemoryJob).where(
                MemoryJob.conversation_id == conversation_id
            )
        ).all()

    assert len(jobs) == 1
    assert jobs[0].status == "pending"
    assert jobs[0].through_seq == messages_by_seq[1]["seq"]


def test_assistant_message_rolls_back_when_memory_job_creation_fails(
    client, monkeypatch
):
    fake_model = FakeListChatModel(
        responses=["This response will not be persisted."]
    )

    monkeypatch.setattr(
        "graph.nodes.chat.get_model",
        lambda: fake_model,
    )

    # Create the user.
    signup_response = client.post(
        "/users/",
        json={
            "email": "atomicity-test@example.com",
            "password": "StrongPassword123!",
        },
    )
    assert signup_response.status_code == 200

    # Log in.
    login_response = client.post(
        "/auth/login",
        json={
            "email": "atomicity-test@example.com",
            "password": "StrongPassword123!",
        },
    )
    assert login_response.status_code == 200

    headers = {
        "Authorization": f"Bearer {login_response.json()['access_token']}"
    }

    # Create a character.
    character_response = client.post(
        "/characters/",
        headers=headers,
        json={
            "name": "Atomicity Test Character",
            "avatar_url": None,
        },
    )
    assert character_response.status_code == 200

    # Create a conversation.
    conversation_response = client.post(
        "/conversations/",
        headers=headers,
        json={
            "character_id": character_response.json()["character_id"]
        },
    )
    assert conversation_response.status_code == 200
    conversation_id = UUID(
        conversation_response.json()["conversation_id"]
    )

    # Simulate failure while enqueuing the memory job.
    def fail_job_creation(*args, **kwargs):
        raise RuntimeError("Simulated memory-job failure")

    monkeypatch.setattr(
        "repositories.memory_job_repository.MemoryJobRepository.create",
        fail_job_creation,
    )

    response = client.post(
        f"/conversations/{conversation_id}/chat",
        headers=headers,
        json={"query": "Keep this user message."},
    )

    # The streaming endpoint reports the failure through SSE.
    assert response.status_code == 200
    assert '"type": "error"' in response.text
    assert '"status": 500' in response.text

    # Transaction 1 remains committed. Transaction 2 rolls back.
    with SessionLocal() as db:
        messages = db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.seq)
        ).all()

        jobs = db.scalars(
            select(MemoryJob).where(
                MemoryJob.conversation_id == conversation_id
            )
        ).all()

    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content == "Keep this user message."
    assert jobs == []


def test_user_message_persists_when_llm_fails(client, monkeypatch):
    class FailingModel:
        def invoke(self, prompt, *args, **kwargs):
            raise RuntimeError("Simulated LLM failure")

    monkeypatch.setattr(
        "graph.nodes.chat.get_model",
        lambda: FailingModel(),
    )

    # Create the user.
    signup_response = client.post(
        "/users/",
        json={
            "email": "llm-failure-test@example.com",
            "password": "StrongPassword123!",
        },
    )
    assert signup_response.status_code == 200

    # Log in.
    login_response = client.post(
        "/auth/login",
        json={
            "email": "llm-failure-test@example.com",
            "password": "StrongPassword123!",
        },
    )
    assert login_response.status_code == 200

    headers = {
        "Authorization": f"Bearer {login_response.json()['access_token']}"
    }

    # Create a character.
    character_response = client.post(
        "/characters/",
        headers=headers,
        json={
            "name": "LLM Failure Test Character",
            "avatar_url": None,
        },
    )
    assert character_response.status_code == 200

    # Create a conversation.
    conversation_response = client.post(
        "/conversations/",
        headers=headers,
        json={
            "character_id": character_response.json()["character_id"]
        },
    )
    assert conversation_response.status_code == 200

    conversation_id = UUID(
        conversation_response.json()["conversation_id"]
    )

    # Send a message while the LLM is failing.
    response = client.post(
        f"/conversations/{conversation_id}/chat",
        headers=headers,
        json={"query": "Remember this even if the model fails."},
    )

    # The streaming endpoint reports the failure through SSE.
    assert response.status_code == 200
    assert '"type": "error"' in response.text
    assert '"status": 500' in response.text

    # The user message must persist; no assistant message or job is created.
    with SessionLocal() as db:
        messages = db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.seq)
        ).all()

        jobs = db.scalars(
            select(MemoryJob).where(
                MemoryJob.conversation_id == conversation_id
            )
        ).all()

    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content == (
        "Remember this even if the model fails."
    )
    assert jobs == []