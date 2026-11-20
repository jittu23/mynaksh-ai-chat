
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.database import (
    init_db,
    get_recent_history,
    save_message,
)
from app.memory import remember, retrieve_relevant_memories
from app.llm import generate_response
from app.schemas import ChatRequest, ChatResponse


# Configure application logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("SQLite database initialized successfully")
    yield


app = FastAPI(
    title="MyNaksh Personalized AI Chat",
    lifespan=lifespan,
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):

    logger.info(
        "Chat request received: user_id=%s, session_id=%s",
        request.user_id,
        request.session_id,
    )

    # Step 1: Retrieve recent conversation history
    history = get_recent_history(
        request.user_id,
        request.session_id,
    )

    # Step 2: Extract and save useful user memories
    remember(request.user_id, request.message)

    # Step 3: Retrieve relevant long-term memories
    memories = retrieve_relevant_memories(
        request.user_id,
        request.message,
    )

    logger.info(
        "Retrieved %d recent messages and %d relevant memories",
        len(history),
        len(memories),
    )

    # Step 4: Generate a personalized LLM response
    try:
        answer = generate_response(
            request.message,
            history,
            memories,
        )

    except Exception as exc:
        logger.exception(
            "LLM provider request failed: %s",
            type(exc).__name__,
        )

        raise HTTPException(
            status_code=502,
            detail="LLM provider request failed",
        ) from exc

    # Step 5: Save the conversation
    save_message(
        request.user_id,
        request.session_id,
        "user",
        request.message,
    )

    save_message(
        request.user_id,
        request.session_id,
        "assistant",
        answer,
    )

    logger.info("Chat response generated successfully")

    # Step 6: Return the response
    return ChatResponse(
        user_id=request.user_id,
        session_id=request.session_id,
        response=answer,
        context_used=[
            memory["memory_type"]
            for memory in memories
        ],
    )
