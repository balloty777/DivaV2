from langchain_core.messages import SystemMessage,HumanMessage
from pydantic import BaseModel,Field
from typing import TypedDict,Literal
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
load_dotenv()
class CharacterSummary(BaseModel):
    name: str=Field(description='The name of the character')
    personality: list[str]=Field(default_factory=list,description='The overall personality of the character')
    physical_features: list[str]=Field(default_factory=list,description='The physical features of the character')
    clothing: list[str]=Field(default_factory=list,description='The clothing of the character')
    background: list[str]=Field(default_factory=list,description='The background story of the character')
    speaking_style: list[str]=Field(default_factory=list,description='The speaking style of the character')
    likes: list[str]=Field(default_factory=list,description='The Likings of the character')
    dislikes: list[str]=Field(default_factory=list,description='The disikings of the character')
    abilities: list[str]=Field(default_factory=list,description='The Abilities of the character')
    weaknesses: list[str]=Field(default_factory=list,description='The weaknesses of the character')
    values: list[str]=Field(default_factory=list,description='The values of the character')
    boundaries: list[str]=Field(default_factory=list,description='The boundaries of the character')
    aliases: list[str] = Field(default_factory=list,description="Nicknames or alternate names.")
    relationships: list[str] = Field(default_factory=list,description="Permanent relationships with other characters.")
    role: list[str] = Field(default_factory=list,description="The character's role in the story or universe.")
class StoredCharacterSummary(CharacterSummary):
    schema_version:Literal[1]=1
class Characters(BaseModel):
    characters:list[CharacterSummary] = Field(description="List of all characters extracted from the user's description.")
def create_character(summary:str)->Characters:
    model=ChatOpenAI(model='gpt-4o')
    prompt=[
        SystemMessage(content=
        """
        You are an expert at extracting and organizing character information for a roleplay chatbot.
        Your task is to read the user's character description and create a structured Character Summary.
        Rules:
        1. Extract only information explicitly stated or strongly implied.
        2. Do not invent personality traits, abilities, history, or relationships.
        3. Preserve the user's intended characterization.
        4. Keep descriptions concise while retaining important details.
        5. If a field has no information, leave it empty.
        6. Do not rewrite the character creatively or improve the writing.
        7. Separate permanent character traits from temporary situations.
        8. Ignore information about the current conversation or story events.
        9. Treat this as the character's permanent profile.
        10. Return only the structured output. 
        11. If the description contains multiple characters, extract each one separately.
        """),
        HumanMessage(content=
        f""" 
        User Character Description:\n
        {summary}
         """)
    ]
    model_with_structure=model.with_structured_output(Characters)
    result=model_with_structure.invoke(prompt)
    return result
    
