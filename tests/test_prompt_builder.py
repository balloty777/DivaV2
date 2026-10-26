
from schemas.conversation_character_summary import ConversationCharacterState
from prompts.prompt_builder import create_final_prompt


def test_prompt_includes_private_conversation_state():
    state = {
        "character_summary": None,
        "character_state": ConversationCharacterState(
            mood="curious",
            trust=0.7,
            familiarity=0.6,
            relationship_stage="close",
        ),
        "short_term_memory": None,
        "long_term_memory": None,
    }

    prompt = create_final_prompt(state)

    assert "# PRIVATE CONVERSATION STATE" in prompt
    assert '"mood": "curious"' in prompt
    assert '"trust": 0.7' in prompt
    assert '"familiarity": 0.6' in prompt
    assert '"relationship_stage": "close"' in prompt


def test_prompt_handles_missing_private_conversation_state():
    state = {
        "character_summary": None,
        "character_state": None,
        "short_term_memory": None,
        "long_term_memory": None,
    }

    prompt = create_final_prompt(state)

    assert "# PRIVATE CONVERSATION STATE" in prompt
    assert "No private conversation state is available." in prompt
    assert "# SHORT-TERM MEMORY" in prompt
    assert "# LONG-TERM MEMORY" in prompt
    assert "# RESPONSE RULES" in prompt
