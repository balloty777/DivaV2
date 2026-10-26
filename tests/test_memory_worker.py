from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import UUID
from schemas.conversation_character_summary import ConversationCharacterState
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from sqlalchemy import select
from models.long_term_memory import LongTermMemory
from models.short_term_memory import ShortTermMemory

from tests.conftest import TestingSessionLocal
from memory import worker
from models.conversation import Conversation
from models.memory_job import MemoryJob
from models.message import Message
from repositories.memory_job_repository import (
    LEASE_DURATION,
    MemoryJobRepository,
)


def _create_conversation(client, monkeypatch):
    """Create a user, character, and conversation through the API."""

    user_response = client.post(
        "/users/",
        json={
            "email": "memory-worker-test@example.com",
            "username": "memory_worker_test",
            "password": "TestPassword123!",
        },
    )
    assert user_response.status_code in (200, 201), user_response.text

    login_response = client.post(
        "/auth/login",
        json={
            "email": "memory-worker-test@example.com",
            "password": "TestPassword123!",
        },
    )
    assert login_response.status_code == 200, login_response.text

    token = login_response.json().get("access_token")
    assert token

    headers = {"Authorization": f"Bearer {token}"}

    character_response = client.post(
        "/characters/",
        headers=headers,
        json={
            "name": "Memory Worker Test Character",
            "description": "A character used to test memory processing.",
            "summary": {},
        },
    )
    assert character_response.status_code in (200, 201), character_response.text

    character_data = character_response.json()
    character_id = character_data.get(
        "character_id",
        character_data.get("id"),
    )
    assert character_id

    conversation_response = client.post(
        "/conversations/",
        headers=headers,
        json={"character_id": character_id},
    )
    assert conversation_response.status_code in (200, 201), (
        conversation_response.text
    )

    conversation_data = conversation_response.json()
    conversation_id = conversation_data.get(
        "conversation_id",
        conversation_data.get("id"),
    )
    assert conversation_id

    return headers, str(conversation_id)


def _create_test_memory_job(conversation_id, through_seq=2):
    """Create a memory job using the actual repository interface."""

    with TestingSessionLocal.begin() as session:
        repository = MemoryJobRepository(session)
        job = repository.create(
            conversation_id=UUID(conversation_id),
            through_seq=through_seq,
        )
        return job.job_id


def test_failed_stm_call_leaves_memory_job_retryable(
    client,
    monkeypatch,
):
    """An STM generation failure should leave the job retryable."""

    headers, conversation_id = _create_conversation(client, monkeypatch)

    fake_model = FakeListChatModel(responses=["A test reply."])
    monkeypatch.setattr(
        "graph.nodes.update_character_state.get_model",
        lambda: FakeCharacterStateModel(),
    )

    chat_response = client.post(
        f"/conversations/{conversation_id}/chat",
        headers=headers,
        json={"query": "Remember this exchange."},
    )
    assert chat_response.status_code == 200, chat_response.text


    def fail_stm(*args, **kwargs):
        raise RuntimeError("Simulated STM LLM failure")

    monkeypatch.setattr(worker, "create_short_term_memory", fail_stm)

    with patch.object(worker, "create_long_term_memory") as ltm_generator:
        assert worker.run_one_memory_job() is True
        ltm_generator.assert_not_called()

    with TestingSessionLocal() as session:
        job = session.execute(
            select(MemoryJob).where(
                MemoryJob.conversation_id == UUID(conversation_id)
            )
        ).scalar_one()

        conversation = session.execute(
            select(Conversation).where(
                Conversation.conversation_id == UUID(conversation_id)
            )
        ).scalar_one()

        messages = session.execute(
            select(Message)
            .where(Message.conversation_id == UUID(conversation_id))
            .order_by(Message.seq)
        ).scalars().all()

        assert job.status == "pending"
        assert job.last_error is not None
        assert "Simulated STM LLM failure" in job.last_error
        assert job.next_attempt_at is not None

        next_attempt = job.next_attempt_at
        if next_attempt.tzinfo is None:
            next_attempt = next_attempt.replace(tzinfo=timezone.utc)

        assert next_attempt > datetime.now(timezone.utc)

        assert conversation.last_stm_seq == 0
        assert conversation.last_ltm_seq == 0

        assert len(messages) == 2
        assert {message.role for message in messages} == {
            "user",
            "assistant",
        }

def test_failed_ltm_call_does_not_persist_stm_or_advance_checkpoints(
    client,
    monkeypatch,
):
    """An LTM generation failure must not partially persist memory."""

    headers, conversation_id = _create_conversation(client, monkeypatch)

    monkeypatch.setattr(
        "graph.nodes.update_character_state.get_model",
        lambda: FakeCharacterStateModel(),
    )

    chat_response = client.post(
        f"/conversations/{conversation_id}/chat",
        headers=headers,
        json={"query": "Remember this exchange."},
    )
    assert chat_response.status_code == 200, chat_response.text

    def generate_stm(*args, **kwargs):
        # The worker must not persist this result if LTM generation fails.
        return object()

    def fail_ltm(*args, **kwargs):
        raise RuntimeError("Simulated LTM LLM failure")

    monkeypatch.setattr(worker, "create_short_term_memory", generate_stm)
    monkeypatch.setattr(worker, "create_long_term_memory", fail_ltm)

    assert worker.run_one_memory_job() is True

    with TestingSessionLocal() as session:
        job = session.execute(
            select(MemoryJob).where(
                MemoryJob.conversation_id == UUID(conversation_id)
            )
        ).scalar_one()

        conversation = session.execute(
            select(Conversation).where(
                Conversation.conversation_id == UUID(conversation_id)
            )
        ).scalar_one()

        stm = session.execute(
            select(ShortTermMemory).where(
                ShortTermMemory.conversation_id == UUID(conversation_id)
            )
        ).scalar_one_or_none()

        ltm = session.execute(
            select(LongTermMemory).where(
                LongTermMemory.conversation_id == UUID(conversation_id)
            )
        ).scalar_one_or_none()

        assert job.status == "pending"
        assert job.last_error is not None
        assert "Simulated LTM LLM failure" in job.last_error
        assert job.next_attempt_at is not None

        assert conversation.last_stm_seq == 0
        assert conversation.last_ltm_seq == 0

        assert stm is None
        assert ltm is None

def test_worker_with_expired_lease_cannot_persist_memory(
    client,
    monkeypatch,
):
    """A worker that loses its lease must not persist stale results."""

    headers, conversation_id = _create_conversation(client, monkeypatch)

    monkeypatch.setattr(
        "graph.nodes.update_character_state.get_model",
        lambda: FakeCharacterStateModel(),
    )

    chat_response = client.post(
        f"/conversations/{conversation_id}/chat",
        headers=headers,
        json={"query": "Remember this exchange."},
    )
    assert chat_response.status_code == 200, chat_response.text

    original_stm_generator = worker.create_short_term_memory
    original_ltm_generator = worker.create_long_term_memory

    def generate_stm_then_expire_lease(*args, **kwargs):
        result = original_stm_generator(*args, **kwargs)

        # Simulate another worker reclaiming the job while this worker
        # is outside its database transaction calling the LLM.
        with TestingSessionLocal.begin() as session:
            job = session.execute(
                select(MemoryJob).where(
                    MemoryJob.conversation_id == UUID(conversation_id)
                )
            ).scalar_one()

            job.status = "processing"
            job.attempts += 1
            job.locked_at = datetime.now(timezone.utc) + timedelta(seconds=1)

        return result

    monkeypatch.setattr(
        worker,
        "create_short_term_memory",
        generate_stm_then_expire_lease,
    )

    # Ensure LTM generation can finish, so the worker reaches the
    # persistence boundary and must reject its stale lease.
    assert callable(original_ltm_generator)

    assert worker.run_one_memory_job() is True

    with TestingSessionLocal() as session:
        job = session.execute(
            select(MemoryJob).where(
                MemoryJob.conversation_id == UUID(conversation_id)
            )
        ).scalar_one()

        conversation = session.execute(
            select(Conversation).where(
                Conversation.conversation_id == UUID(conversation_id)
            )
        ).scalar_one()

        stm = session.execute(
            select(ShortTermMemory).where(
                ShortTermMemory.conversation_id == UUID(conversation_id)
            )
        ).scalar_one_or_none()

        ltm = session.execute(
            select(LongTermMemory).where(
                LongTermMemory.conversation_id == UUID(conversation_id)
            )
        ).scalar_one_or_none()

        assert job.status == "processing"

        # The newer lease must remain untouched.
        assert job.attempts == 2
        assert job.locked_at is not None

        # The stale worker must not persist memory or advance checkpoints.
        assert stm is None
        assert ltm is None
        assert conversation.last_stm_seq == 0
        assert conversation.last_ltm_seq == 0
def test_memory_job_enqueue_coalesces_through_seq(
    client,
    monkeypatch,
):
    """Repeated enqueues should update one active job to the newest sequence."""

    _, conversation_id = _create_conversation(client, monkeypatch)
    conversation_uuid = UUID(conversation_id)

    with TestingSessionLocal.begin() as session:
        repository = MemoryJobRepository(session)
        first_job = repository.create(
            conversation_id=conversation_uuid,
            through_seq=2,
        )
        first_job_id = first_job.job_id

    with TestingSessionLocal.begin() as session:
        repository = MemoryJobRepository(session)
        second_job = repository.create(
            conversation_id=conversation_uuid,
            through_seq=5,
        )
        second_job_id = second_job.job_id

    with TestingSessionLocal() as session:
        jobs = session.execute(
            select(MemoryJob).where(
                MemoryJob.conversation_id == conversation_uuid,
                MemoryJob.status.in_(("pending", "processing")),
            )
        ).scalars().all()

        assert first_job_id == second_job_id
        assert len(jobs) == 1
        assert jobs[0].through_seq == 5
        assert jobs[0].status == "pending"


def test_claim_next_job_claims_pending_job(client, monkeypatch):
    """Claiming a pending job sets its lease and increments attempts."""

    _, conversation_id = _create_conversation(client, monkeypatch)

    job_id = _create_test_memory_job(conversation_id)

    with TestingSessionLocal.begin() as session:
        repository = MemoryJobRepository(session)
        claimed = repository.claim_next_job()

        assert claimed is not None
        assert claimed.job_id == job_id
        assert claimed.status == "processing"
        assert claimed.attempts == 1
        assert claimed.locked_at is not None
        assert claimed.next_attempt_at is None


def test_claim_next_job_respects_retry_time(client, monkeypatch):
    """A pending job must not be claimed before its retry time."""

    _, conversation_id = _create_conversation(client, monkeypatch)    

    job_id = _create_test_memory_job(conversation_id)

    with TestingSessionLocal.begin() as session:
        job = session.get(MemoryJob, job_id)
        job.next_attempt_at = (
            datetime.now(timezone.utc) + timedelta(minutes=10)
        )

    with TestingSessionLocal.begin() as session:
        repository = MemoryJobRepository(session)
        claimed = repository.claim_next_job()

        assert claimed is None

    with TestingSessionLocal() as session:
        job = session.get(MemoryJob, job_id)
        assert job.status == "pending"
        assert job.attempts == 0


def test_claim_next_job_reclaims_expired_lease(client, monkeypatch):
    """A processing job with an expired lease can be reclaimed."""

    _, conversation_id = _create_conversation(client, monkeypatch)

    job_id = _create_test_memory_job(conversation_id)
    expired_time = (
        datetime.now(timezone.utc)
        - LEASE_DURATION
        - timedelta(seconds=1)
    )

    with TestingSessionLocal.begin() as session:
        job = session.get(MemoryJob, job_id)
        job.status = "processing"
        job.attempts = 1
        job.locked_at = expired_time

    with TestingSessionLocal.begin() as session:
        repository = MemoryJobRepository(session)
        claimed = repository.claim_next_job()

        assert claimed is not None
        assert claimed.job_id == job_id
        assert claimed.status == "processing"
        assert claimed.attempts == 2
        assert claimed.locked_at is not None
        assert claimed.locked_at > expired_time


def test_claim_next_job_fails_expired_job_at_attempt_limit(
    client,
    monkeypatch,
):
    """An expired lease at the attempt limit becomes terminally failed."""

    _, conversation_id = _create_conversation(client, monkeypatch)


    job_id = _create_test_memory_job(conversation_id)
    expired_time = (
        datetime.now(timezone.utc)
        - LEASE_DURATION
        - timedelta(seconds=1)
    )

    with TestingSessionLocal.begin() as session:
        job = session.get(MemoryJob, job_id)
        job.status = "processing"
        job.attempts = job.max_attempts
        job.locked_at = expired_time

    with TestingSessionLocal.begin() as session:
        repository = MemoryJobRepository(session)
        claimed = repository.claim_next_job()

        assert claimed is None

    with TestingSessionLocal() as session:
        job = session.get(MemoryJob, job_id)
        assert job.status == "failed"
        assert job.locked_at is None
        assert job.next_attempt_at is None
        assert "lease expired" in job.last_error.lower()


def test_claim_next_job_returns_none_when_no_jobs_exist(
    client,
    monkeypatch,
):
    """The worker should have nothing to claim when no jobs exist."""

    _, conversation_id = _create_conversation(client, monkeypatch)

    with TestingSessionLocal.begin() as session:
        repository = MemoryJobRepository(session)
        claimed = repository.claim_next_job()

        assert claimed is None


def test_mark_completed_marks_job_completed(client, monkeypatch):
    _, conversation_id = _create_conversation(client, monkeypatch)
    job_id = _create_test_memory_job(conversation_id, through_seq=2)

    with TestingSessionLocal.begin() as session:
        repository = MemoryJobRepository(session)
        claimed = repository.claim_next_job()
        assert claimed is not None
        assert claimed.job_id == job_id

        completed = repository.mark_completed(job_id, processed_through_seq=2)
        assert completed is True

    with TestingSessionLocal() as session:
        job = session.get(MemoryJob, job_id)
        assert job.status == "completed"
        assert job.locked_at is None
        assert job.next_attempt_at is None
        assert job.last_error is None


def test_mark_completed_requeues_when_through_seq_advances(
    client, monkeypatch
):
    _, conversation_id = _create_conversation(client, monkeypatch)
    job_id = _create_test_memory_job(conversation_id, through_seq=2)

    with TestingSessionLocal.begin() as session:
        repository = MemoryJobRepository(session)
        claimed = repository.claim_next_job()
        assert claimed is not None

        # Simulate newer messages being coalesced into the active job.
        claimed.through_seq = 5

        completed = repository.mark_completed(
            job_id, processed_through_seq=2
        )
        assert completed is False

    with TestingSessionLocal() as session:
        job = session.get(MemoryJob, job_id)
        assert job.status == "pending"
        assert job.through_seq == 5
        assert job.locked_at is None


def test_mark_failed_schedules_exponential_retry(client, monkeypatch):
    _, conversation_id = _create_conversation(client, monkeypatch)
    job_id = _create_test_memory_job(conversation_id)

    with TestingSessionLocal.begin() as session:
        repository = MemoryJobRepository(session)
        claimed = repository.claim_next_job()
        assert claimed is not None

        before = datetime.now(timezone.utc)
        failed = repository.mark_failed(job_id, "simulated failure")
        after = datetime.now(timezone.utc)

        assert failed.status == "pending"
        assert failed.last_error == "simulated failure"
        assert failed.locked_at is None
        assert failed.next_attempt_at is not None

        retry_at = failed.next_attempt_at
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)

        # First failed attempt uses the repository's 5-second base delay.
        assert before + timedelta(seconds=5) <= retry_at
        assert retry_at <= after + timedelta(seconds=5)


def test_mark_failed_becomes_terminal_at_attempt_limit(
    client, monkeypatch
):
    _, conversation_id = _create_conversation(client, monkeypatch)
    job_id = _create_test_memory_job(conversation_id)

    with TestingSessionLocal.begin() as session:
        job = session.get(MemoryJob, job_id)
        job.status = "processing"
        job.attempts = job.max_attempts
        job.locked_at = datetime.now(timezone.utc)

        repository = MemoryJobRepository(session)
        failed = repository.mark_failed(job_id, "final failure")

        assert failed.status == "failed"
        assert failed.last_error == "final failure"
        assert failed.locked_at is None
        assert failed.next_attempt_at is None
