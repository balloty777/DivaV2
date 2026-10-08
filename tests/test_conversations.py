def test_create_conversation(client):
    # Create the user who will own the conversation.
    signup_response = client.post(
        "/users/",
        json={
            "email": "conversation-test@example.com",
            "password": "StrongPassword123!",
        },
    )

    assert signup_response.status_code == 200

    user_id = signup_response.json()["user_id"]

    # Log in to obtain the V1 JWT.
    login_response = client.post(
        "/auth/login",
        json={
            "email": "conversation-test@example.com",
            "password": "StrongPassword123!",
        },
    )

    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    # Create the character that the conversation will belong to.
    character_response = client.post(
        "/characters/",
        headers=headers,
        json={
            "name": "Conversation Test Character",
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

    data = conversation_response.json()

    assert "conversation_id" in data
    assert data["user_id"] == user_id
    assert data["character_id"] == character_id
    assert data["status"] == "active"
    assert data["title"] is None
    assert "created_at" in data
    assert "updated_at" in data