
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from sqlalchemy import select

from models.conversation_character_summary import (
    ConversationCharacterSummary,
)
from models.user import User
from models.character import Character
from services.conversation_service import ConversationService
from repositories.conversation_character_summary_repository import (
    ConversationCharacterSummaryRepository,
)
from tests.conftest import TestingSessionLocal


def test_character_state_row_lock_blocks_second_transaction(db_session):
    user_id = uuid4()
    character_id = uuid4()

    user = User(
        user_id=user_id,
        email="row-lock-test@example.com",
        password_hash="test-password-hash",
    )

    character = Character(
        character_id=character_id,
        creator_id=user_id,
        name="Row Lock Character",
        status="active",
        version=1,
    )

    db_session.add_all([user, character])
    db_session.commit()

    conversation = ConversationService(db_session).create_conversation(
        current_user_id=user_id,
        character_id=character_id,
    )
    conversation_id = conversation.conversation_id
    db_session.commit()

    lock_acquired = threading.Event()
    release_first_transaction = threading.Event()
    second_transaction_started = threading.Event()
    second_lock_acquired = threading.Event()

    def first_transaction():
        with TestingSessionLocal() as db:
            with db.begin():
                repository = ConversationCharacterSummaryRepository(db)

                row = repository.get_by_conversation_id_for_update(
                    conversation_id
                )
                assert row is not None

                lock_acquired.set()

                if not release_first_transaction.wait(timeout=10):
                    raise TimeoutError(
                        "Timed out waiting to release the first row lock."
                    )

    def second_transaction():
        if not lock_acquired.wait(timeout=10):
            raise TimeoutError("First transaction did not acquire its lock.")

        with TestingSessionLocal() as db:
            with db.begin():
                second_transaction_started.set()

                repository = ConversationCharacterSummaryRepository(db)

                row = repository.get_by_conversation_id_for_update(
                    conversation_id
                )
                assert row is not None

                second_lock_acquired.set()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(first_transaction)

        try:
            assert lock_acquired.wait(timeout=10)

            second_future = executor.submit(second_transaction)

            assert second_transaction_started.wait(timeout=10)

            # Give PostgreSQL time to process the second lock request.
            time.sleep(0.3)

            assert not second_lock_acquired.is_set(), (
                "The second transaction acquired the row lock while "
                "the first transaction was still holding it."
            )
        finally:
            release_first_transaction.set()

        first_future.result(timeout=10)
        second_future.result(timeout=10)

    assert second_lock_acquired.is_set()
