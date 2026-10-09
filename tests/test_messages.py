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

    # Log in to obtain the JWT.
    login_response = client.post(
        "/auth/login",
        json={
            "email": "message-test@example.com",
            "password": "StrongPassword123!",
        },
    )

    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

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
        json={"character_id": character_id},
    )

    assert conversation_response.status_code == 200
    conversation_id = conversation_response.json()["conversation_id"]

    # Retrieve messages from the new, empty conversation.
    messages_response = client.get(
        f"/conversations/{conversation_id}/messages/",
        headers=headers,
    )

    assert messages_response.status_code == 200
    assert messages_response.json() == []