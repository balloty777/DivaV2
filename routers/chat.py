import json
import logging
from uuid import UUID
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage
from sqlalchemy.orm import Session
from auth.dependencies import get_current_user
from database.dependencies import get_db
from exceptions.application import ForbiddenException, NotFoundException
from graph.graph import chatbot
from models.user import User
from schemas.chat import ChatRequest
from services.conversation_service import ConversationService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversations",tags=["Chat"])


@router.post("/{conversation_id}/chat")
def chat(conversation_id: UUID,data: ChatRequest,current_user: User = Depends(get_current_user),db: Session = Depends(get_db)) -> StreamingResponse:
    conversation_service = ConversationService(db)
    conversation_service.get_conversation(current_user_id=current_user.user_id,conversation_id=conversation_id)
    config = {"configurable": {"db": db,"current_user_id": current_user.user_id}}
    def sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    def event_stream():
        try:
            for chunk, metadata in chatbot.stream(
                {"conversation_id": conversation_id,"query": data.query},config=config,stream_mode="messages"):
                if metadata.get("langgraph_node") != "chat":
                    continue
                if isinstance(chunk, AIMessage) and chunk.content:
                    yield sse({"type": "token","content": chunk.content})
            db.commit()
            yield sse({"type": "done","conversation_id": str(conversation_id)})
        except NotFoundException as exc:
            db.rollback()
            yield sse({"type": "error","status": 404,"message": str(exc)})
        except ForbiddenException as exc:
            db.rollback()
            yield sse({"type": "error","status": 403,"message": str(exc)})
        except Exception:
            db.rollback()
            logger.exception("Unable to generate a response for conversation %s",conversation_id)
            yield sse({"type": "error","status": 500,"message": "Unable to generate a response."})
    return StreamingResponse(event_stream(),media_type="text/event-stream")