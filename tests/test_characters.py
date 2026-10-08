def test_create_character(client):
    # Create a user first.
    signup_response = client.post(
        "/users/",
        json={
            "email": "character-test@example.com",
            "password": "StrongPassword123!",
        },
    )

    assert signup_response.status_code == 200

    # Log in to obtain the V1 JWT.
    login_response = client.post(
        "/auth/login",
        json={
            "email": "character-test@example.com",
            "password": "StrongPassword123!",
        },
    )

    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]

    # Create a character as the authenticated user.
    character_response = client.post(
        "/characters/",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        json={
            "name": "Test Character",
            "avatar_url": None,
        },
    )

    assert character_response.status_code == 200

    data = character_response.json()

    assert data["name"] == "Test Character"
    assert data["status"] == "active"
    assert data["creator_id"] is not None
    assert "character_id" in data
    assert "created_at" in data
    assert "updated_at" in data