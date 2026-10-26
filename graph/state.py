from typing import TypedDict,Annotated
from pydantic import Field
from uuid import UUID
from langchain_core.messages import BaseMessage
from character.character_summary import Characters
from memory.long_term_memory import LongTermMemory
from memory.short_term_memory import  ShortTermMemory
from schemas.conversation_character_summary import ConversationCharacterState
class State(TypedDict):
    conversation_id:UUID
    query:str 
    messages:list[BaseMessage]
    last_seq:int
    character_summary: Characters | None
    character_state:ConversationCharacterState| None
    short_term_memory: ShortTermMemory | None
    long_term_memory: LongTermMemory | None
    response:str 