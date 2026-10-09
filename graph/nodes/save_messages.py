from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from exceptions.application import NotFoundException
from graph.state import State
from repositories.conversation_repository import ConversationRepository
from repositories.message_repository import MessageRepository

def save_messages(state: State, config: RunnableConfig) -> dict:
    configurable = config.get("configurable", {})
    db = configurable.get("db")
    current_user_id = configurable.get("current_user_id")
    if db is None or current_user_id is None:
        raise RuntimeError("Graph config must include both 'db' and 'current_user_id'.")
    conversation_id = state["conversation_id"]
    conversation = ConversationRepository(db).get_by_id(user_id=current_user_id,conversation_id=conversation_id)
    if conversation is None:
        raise NotFoundException("Conversation does not exist")
    repository = MessageRepository(db)
    repository.store_message(conversation_id=conversation_id,role="user",content=state["query"])
    repository.store_message(conversation_id=conversation_id,role="assistant",content=state["response"])
    db.flush()
    return {"messages": [*state.get("messages", []),HumanMessage(content=state["query"]),AIMessage(content=state["response"])]}
