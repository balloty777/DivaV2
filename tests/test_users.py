def test_create_user(client):
    response = client.post(
        "/users/",
        json={
            "email": "test@example.com",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["email"] == "test@example.com"
    assert "user_id" in data
    assert "created_at" in data
    assert "updated_at" in data

    assert "password" not in data
    assert "password_hash" not in data