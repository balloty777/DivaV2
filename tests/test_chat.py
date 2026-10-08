import json

from langchain_core.language_models.fake_chat_models import FakeListChatModel


def test_chat(client, monkeypatch):
    # Replace the real OpenRouter model with a deterministic fake.
    fake_model = FakeListChatModel(
        responses=["This is a test response."]
    )

    monkeypatch.setattr(
        "graph.nodes.chat.get_model",
        lambda: fake_model,
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

    access_token = login_response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {access_token}",
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
        json={
            "character_id": character_id,
        },
    )

    assert conversation_response.status_code == 200

    conversation_id = conversation_response.json()["conversation_id"]

    # Send a chat request.
    chat_response = client.post(
        f"/conversations/{conversation_id}/chat",
        headers=headers,
        json={
            "query": "Hello!",
        },
    )

    assert chat_response.status_code == 200
    assert chat_response.headers["content-type"].startswith(
        "text/event-stream"
    )

    response_text = chat_response.text

    # The V1 endpoint should stream the assistant response.
    assert '"type": "token"' in response_text

    token_content = ""

    for line in response_text.splitlines():
        if line.startswith("data: "):
            event = json.loads(line[6:])

            if event["type"] == "token":
                token_content += event["content"]

    assert token_content == "This is a test response."

    # The V1 endpoint should finish with a done event.
    assert '"type": "done"' in response_text
    assert str(conversation_id) in response_text

    # Verify that V1 persisted both sides of the chat turn.
    messages_response = client.get(
        f"/conversations/{conversation_id}/messages/",
        headers=headers,
    )

    assert messages_response.status_code == 200

    messages = messages_response.json()

    assert len(messages) == 2

    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello!"

    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "This is a test response."