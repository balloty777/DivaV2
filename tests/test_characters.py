from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import select

from character.character_summary import CharacterSummary, Characters
from models.character_summary import CharacterSummary as CharacterSummaryRecord
from services.character_service import CharacterService


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

    # Log in to obtain the JWT.
    login_response = client.post(
        "/auth/login",
        json={
            "email": "character-test@example.com",
            "password": "StrongPassword123!",
        },
    )

    assert login_response.status_code == 200

    headers = {
        "Authorization": f"Bearer {login_response.json()['access_token']}",
    }

    # Create a regular character through the API.
    character_response = client.post(
        "/characters/",
        headers=headers,
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


def test_create_character_from_summary_saves_canonical_profile(db_session):
    """Summary-based character creation stores the canonical JSON format."""
    user_id = uuid4()

    # Create a real user so the service can validate the creator.
    from models.user import User

    user = User(
        user_id=user_id,
        email="canonical-profile@example.com",
        password_hash="test-password-hash",
    )
    db_session.add(user)
    db_session.commit()

    extracted_profile = CharacterSummary(
        name="Temporary Name",
        personality=["Quiet", "Observant"],
    )

    extracted_characters = Characters(
        characters=[extracted_profile]
    )

    with patch(
        "services.character_service.create_character",
        return_value=extracted_characters,
    ):
        service = CharacterService(db_session)

        character = service.create_character_from_summary(
            creator_id=user_id,
            name="Aria",
            summary="A quiet and observant character.",
        )

    summary = db_session.scalar(
        select(CharacterSummaryRecord).where(
            CharacterSummaryRecord.character_id == character.character_id
        )
    )

    assert summary is not None

    content = summary.content

    assert content["schema_version"] == 1
    assert content["name"] == "Aria"
    assert content["personality"] == ["Quiet", "Observant"]
    assert "characters" not in content

    expected_fields = {
        "personality",
        "physical_features",
        "clothing",
        "background",
        "speaking_style",
        "likes",
        "dislikes",
        "abilities",
        "weaknesses",
        "values",
        "boundaries",
        "aliases",
        "relationships",
        "role",
    }

    assert expected_fields.issubset(content.keys())
