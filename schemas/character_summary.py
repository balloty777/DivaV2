from pydantic import BaseModel,ConfigDict
from character.character_summary import StoredCharacterSummary
class CharacterSummaryCreate(BaseModel):
    model_config=ConfigDict(extra="forbid")
    content:StoredCharacterSummary