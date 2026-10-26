import logging
from uuid import UUID
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select
from database.db import SessionLocal
from memory.long_term_memory import LongTermMemory as LongTermMemorySchema,create_long_term_memory
from memory.short_term_memory import ShortTermMemory as ShortTermMemorySchema,create_short_term_memory
from models.conversation import Conversation
from models.long_term_memory import LongTermMemory
from models.memory_job import MemoryJob
from models.short_term_memory import ShortTermMemory
from repositories.long_term_memory_repository import LongTermMemoryRepository
from repositories.memory_job_repository import MemoryJobRepository
from repositories.message_repository import MessageRepository
from repositories.short_term_memory_repository import ShortTermMemoryRepository

logger = logging.getLogger(__name__)


def _to_langchain_messages(rows):

    return [
        HumanMessage(content=row.content)
        if row.role == "user"
        else AIMessage(content=row.content)
        for row in rows
    ]


def run_one_memory_job() -> bool:

    job_id: UUID | None = None
    claimed_locked_at = None

    with SessionLocal() as db:
        with db.begin():
            repository = MemoryJobRepository(db)
            job = repository.claim_next_job()
            if job is None:
                return False
            job_id = job.job_id
            conversation_id = job.conversation_id
            claimed_locked_at = job.locked_at

    try:
        with SessionLocal() as db:
            with db.begin():
                job = db.scalar(select(MemoryJob).where(MemoryJob.job_id == job_id))

                if (job is None or job.status != "processing" or job.locked_at != claimed_locked_at):
                    raise RuntimeError("Claimed memory job is no longer owned ""by this worker")
                conversation = db.scalar(
                    select(Conversation).where(Conversation.conversation_id == conversation_id))

                if conversation is None:
                    raise RuntimeError("Conversation for memory job no longer exists")
                target_seq = job.through_seq
                stm_checkpoint = conversation.last_stm_seq
                ltm_checkpoint = conversation.last_ltm_seq

                message_repository = MessageRepository(db)

                stm_rows = (message_repository.get_messages_between_sequences(conversation_id,stm_checkpoint,target_seq))
                ltm_rows = (message_repository.get_messages_between_sequences(conversation_id,ltm_checkpoint,target_seq))

                stm_row = (ShortTermMemoryRepository(db).get_memory_by_conversation_id(conversation_id))
                ltm_row = (LongTermMemoryRepository(db).get_memory_by_conversation_id(conversation_id))

                old_stm = (ShortTermMemorySchema.model_validate(stm_row.content) if stm_row is not None else None)
                old_ltm = (LongTermMemorySchema.model_validate(ltm_row.content) if ltm_row is not None else None)

                stm_messages = _to_langchain_messages(stm_rows)
                ltm_messages = _to_langchain_messages(ltm_rows)

        new_stm = old_stm
        new_ltm = old_ltm

        if stm_messages:
            new_stm = create_short_term_memory(stm_messages,old_stm)

        if ltm_messages:
            new_ltm = create_long_term_memory(ltm_messages,old_ltm)

        with SessionLocal() as db:
            with db.begin():
                job = db.scalar(select(MemoryJob).where(MemoryJob.job_id == job_id).with_for_update())

                if (job is None or job.status != "processing" or job.locked_at != claimed_locked_at):
                    raise RuntimeError("Memory job lease is no longer owned ""by this worker")
                conversation = db.scalar(select(Conversation).where(Conversation.conversation_id == conversation_id).with_for_update())

                if conversation is None:
                    raise RuntimeError("Conversation no longer exists")

                if new_stm is not None:
                    repository = ShortTermMemoryRepository(db)
                    row = repository.get_memory_by_conversation_id(conversation_id)
                    content = new_stm.model_dump(mode="json")
                    if row is None:
                        repository.create_short_term_memory(conversation_id,content)
                    else:
                        repository.update_short_term_memory(row,content)

                if new_ltm is not None:
                    repository = LongTermMemoryRepository(db)
                    row = repository.get_memory_by_conversation_id(conversation_id)
                    content = new_ltm.model_dump(mode="json")
                    if row is None:
                        repository.create_long_term_memory(conversation_id,content)
                    else:
                        repository.update_long_term_memory(row,content)
                conversation.last_stm_seq = max(conversation.last_stm_seq,target_seq)
                conversation.last_ltm_seq = max(conversation.last_ltm_seq,target_seq)
                completed = MemoryJobRepository(db).mark_completed(job_id,target_seq)
                if not completed:
                    logger.info("Memory job %s has more messages to process",job_id)
        return True

    except Exception as exc:
        logger.exception("Memory worker failed for job %s",job_id)

        with SessionLocal() as db:
            with db.begin():
                job = db.scalar(select(MemoryJob).where(MemoryJob.job_id == job_id).with_for_update())
                if (job is not None and job.status == "processing" and job.locked_at == claimed_locked_at):
                    MemoryJobRepository(db).mark_failed(job_id,exc)
                else:
                    logger.warning("Skipping failure update for job %s: ""this worker no longer owns the lease",job_id)

        return True

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    while run_one_memory_job():
        pass