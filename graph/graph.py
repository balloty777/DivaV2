from langgraph.graph import StateGraph, START, END
from graph.nodes.prepare_chat import prepare_chat
from graph.nodes.chat import ChatNode
from graph.nodes.save_assistant_message import save_assistant_message
from graph.state import State
from graph.nodes.update_character_state import update_character_state

app = StateGraph(State)
app.add_node("prepare_chat", prepare_chat)
app.add_node("chat", ChatNode)
app.add_node("save_assistant_message", save_assistant_message)
app.add_node("update_character_state", update_character_state)

app.add_edge(START, "prepare_chat")
app.add_edge("prepare_chat", "chat")
app.add_edge("chat", "save_assistant_message")
app.add_edge("save_assistant_message", "update_character_state")
app.add_edge("update_character_state", END)

chatbot = app.compile()
