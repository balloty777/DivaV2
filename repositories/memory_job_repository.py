from uuid import UUID
from sqlalchemy.orm import Session
from models.memory_job import MemoryJob

class MemoryJobRepository:
    def __init__(self,db:Session):
        self.db=db
    def create(self,conversation_id:UUID,through_seq:int)->MemoryJob:
        job=MemoryJob(conversation_id=conversation_id,through_seq=through_seq,status="pending",attempts=0)
        self.db.add(job)
        self.db.flush()
        return job