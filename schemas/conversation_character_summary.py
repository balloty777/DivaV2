from typing import Literal
from pydantic import BaseModel,ConfigDict,Field

class ConversationCharacterState(BaseModel):
    model_config=ConfigDict(extra="forbid")
    mood:str=Field(default="calm",min_length=1,max_length=100)
    trust:float=Field(default=0.0,ge=0.0,le=1.0)
    familiarity:float=Field(default=0.0,ge=0.0,le=1.0)
    relationship_stage:Literal["new","acquaintance","familiar","close","intimate"]="new"
class ConversationCharacterSummaryCreate(BaseModel):
    model_config=ConfigDict(extra="forbid")
    content : ConversationCharacterState