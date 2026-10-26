from uuid import uuid4

from models.user import User
from models.character import Character
from models.character_summary import CharacterSummary as CharacterSummaryRecord
from models.conversation import Conversation
from services.conversation_service import ConversationService
from services.character_summary_service import CharacterSummaryService
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

def test_conversation_keeps_character_summary_snapshot_after_edit(db_session):
    user_id = uuid4()
    character_id = uuid4()

    user = User(
        user_id=user_id,
        email="snapshot-test@example.com",
        password_hash="test-password-hash",
    )

    character = Character(
        character_id=character_id,
        creator_id=user_id,
        name="Aria",
        status="active",
        version=3,
    )

    original_summary = {
        "schema_version": 1,
        "name": "Aria",
        "personality": ["Quiet", "Observant"],
    }

    summary = CharacterSummaryRecord(
        character_id=character_id,
        content=original_summary,
    )

    db_session.add_all([user, character, summary])
    db_session.commit()

    # Create a conversation using the current character version and summary.
    conversation_service = ConversationService(db_session)
    conversation = conversation_service.create_conversation(
        current_user_id=user_id,
        character_id=character_id,
    )

    assert conversation.character_version == 3
    assert conversation.character_summary_snapshot == original_summary

    conversation_id = conversation.conversation_id

    # Edit the character definition after the conversation has started.
    updated_summary = {
        **original_summary,
        "personality": ["Quiet", "Observant", "Protective"],
    }

    CharacterSummaryService(db_session).update_character_summary(
        user_id=user_id,
        character_id=character_id,
        content=updated_summary,
    )

    db_session.refresh(character)
    stored_conversation = db_session.get(Conversation, conversation_id)
    db_session.refresh(stored_conversation)

    assert character.version == 4
    assert stored_conversation.character_version == 3
    assert stored_conversation.character_summary_snapshot == original_summary


def test_load_context_uses_conversation_snapshot_not_latest_summary(db_session):
    from models.user import User
    from models.character import Character
    from models.conversation import Conversation
    from models.character_summary import CharacterSummary as CharacterSummaryRecord
    from graph.nodes.loader import load_context

    user_id = uuid4()
    character_id = uuid4()
    conversation_id = uuid4()

    user = User(
        user_id=user_id,
        email="loader-snapshot-test@example.com",
        password_hash="test-password-hash",
    )

    character = Character(
        character_id=character_id,
        creator_id=user_id,
        name="Aria",
        status="active",
        version=2,
    )

    original_summary = {
        "schema_version": 1,
        "name": "Aria",
        "personality": ["Quiet"],
    }

    latest_summary = {
        "schema_version": 1,
        "name": "Aria",
        "personality": ["Quiet", "Protective"],
    }

    summary_record = CharacterSummaryRecord(
        character_id=character_id,
        content=latest_summary,
    )

    conversation = Conversation(
        conversation_id=conversation_id,
        user_id=user_id,
        character_id=character_id,
        character_version=1,
        character_summary_snapshot=original_summary,
    )

    db_session.add_all([user, character, summary_record, conversation])
    db_session.commit()

    context = load_context(
        {"conversation_id": conversation_id},
        {
            "configurable": {
                "db": db_session,
                "current_user_id": user_id,
            }
        },
    )

    loaded_profile = context["character_summary"].characters[0]

    assert loaded_profile.personality == ["Quiet"]
    assert loaded_profile.personality != latest_summary["personality"]

def test_load_context_uses_private_conversation_character_state(db_session):
    from models.conversation_character_summary import ConversationCharacterSummary
    from graph.nodes.loader import load_context

    user_id = uuid4()
    character_id = uuid4()
    conversation_id = uuid4()

    user = User(
        user_id=user_id,
        email="state-loader-test@example.com",
        password_hash="test-password-hash",
    )

    character = Character(
        character_id=character_id,
        creator_id=user_id,
        name="Aria",
        status="active",
        version=1,
    )

    conversation = Conversation(
        conversation_id=conversation_id,
        user_id=user_id,
        character_id=character_id,
        character_version=1,
        character_summary_snapshot=None,
    )

    private_state = ConversationCharacterSummary(
        conversation_id=conversation_id,
        content={
            "mood": "curious",
            "trust": 0.8,
            "familiarity": 0.6,
            "relationship_stage": "close",
        },
    )

    db_session.add_all([user, character, conversation, private_state])
    db_session.commit()

    context = load_context(
        {"conversation_id": conversation_id},
        {
            "configurable": {
                "db": db_session,
                "current_user_id": user_id,
            }
        },
    )

    loaded_state = context["character_state"]

    assert loaded_state is not None
    assert loaded_state.mood == "curious"
    assert loaded_state.trust == 0.8
    assert loaded_state.familiarity == 0.6
    assert loaded_state.relationship_stage == "close"