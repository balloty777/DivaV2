def test_list_messages(client):
    # Create the user who will own the conversation.
    signup_response = client.post(
        "/users/",
        json={
            "email": "message-test@example.com",
            "password": "StrongPassword123!",
        },
    )

    assert signup_response.status_code == 200

    # Log in to obtain the V1 JWT.
    login_response = client.post(
        "/auth/login",
        json={
            "email": "message-test@example.com",
            "password": "StrongPassword123!",
        },
    )

    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    # Create the character.
    character_response = client.post(
        "/characters/",
        headers=headers,
        json={
            "name": "Message Test Character",
            "avatar_url": None,
        },
    )

    assert character_response.status_code == 200

    character_id = character_response.json()["character_id"]

    # Create the conversation.
    conversation_response = client.post(
        "/conversations/",
        headers=headers,
        json={
            "character_id": character_id,
        },
    )

    assert conversation_response.status_code == 200

    conversation_id = conversation_response.json()["conversation_id"]

    # Store a user message.
    user_message_response = client.post(
        f"/conversations/{conversation_id}/messages/",
        headers=headers,
        json={
            "content": "Hello there!",
            "role": "user",
        },
    )

    assert user_message_response.status_code == 200

    # Store an assistant message.
    assistant_message_response = client.post(
        f"/conversations/{conversation_id}/messages/",
        headers=headers,
        json={
            "content": "Hello! How can I help?",
            "role": "assistant",
        },
    )

    assert assistant_message_response.status_code == 200

    # Retrieve all messages in the conversation.
    messages_response = client.get(
        f"/conversations/{conversation_id}/messages/",
        headers=headers,
    )

    assert messages_response.status_code == 200

    messages = messages_response.json()

    assert len(messages) == 2

    assert messages[0]["content"] == "Hello there!"
    assert messages[0]["role"] == "user"

    assert messages[1]["content"] == "Hello! How can I help?"
    assert messages[1]["role"] == "assistant"

    assert "message_id" in messages[0]
    assert "conversation_id" in messages[0]
    assert "created_at" in messages[0]