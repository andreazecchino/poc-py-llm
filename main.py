import json
import uuid
from asyncio import Lock
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum

from fastapi import FastAPI, status, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel, Field
from ollama import AsyncClient


class Settings(BaseSettings):
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "smollm2:360m-instruct-q4_K_M"
    session_ttl_minutes: int = 30
    max_session_messages: int = 50
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)


class Role(str, Enum):
    user = "user"
    assistant = "assistant"


class Message(BaseModel):
    role: Role
    content: str


class ChatTurn(BaseModel):
    session_id: str
    text: str = Field(
        min_length=1,
        max_length=2000,
        description="Next message in the conversation",
        default="Tell me about your capabilities in one sentence",
    )


class SessionCreated(BaseModel):
    session_id: str


class Services(BaseModel):
    fastapi: str
    ollama: str


class Health(BaseModel):
    status: str
    services: Services


@dataclass
class SessionData:
    messages: list[Message] = field(default_factory=list)
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    lock: Lock = field(default_factory=Lock)


def create_session() -> str:
    session_id = uuid.uuid4().hex
    sessions[session_id] = SessionData()
    return session_id


def get_session(session_id: str) -> SessionData:
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    ttl = timedelta(minutes=settings.session_ttl_minutes)
    if datetime.now(timezone.utc) - session.last_accessed > ttl:
        del sessions[session_id]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    return session


tags_metadata = [
    {
        "name": "Health check",
        "description": "Verify if all services are online",
    },
    {
        "name": "Chat sessions",
        "description": "Create and inspect conversation sessions",
    },
    {
        "name": "Text generation",
        "description": "Use a Ollama model to generate a text response",
    },
]

app = FastAPI(
    title="POC with Python, FastAPI and Ollama",
    description="Practical proof-of-concept to test AI text generation using constrained computing resources.",
    version="0.1.0",
    openapi_tags=tags_metadata,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    # allow_headers=["*"], # TODO: set specific headers
)
settings = Settings()
ollama_client = AsyncClient(host=settings.ollama_host)
sessions: dict[str, SessionData] = {}


@app.get(
    "/health",
    tags=["Health check"],
    response_model=Health,
    status_code=status.HTTP_200_OK,
)
async def health_check():
    health_status = Health(
        status="healthy", services=Services(fastapi="online", ollama="unknown")
    )

    try:
        await ollama_client.list()
        health_status.services.ollama = "online"
    except Exception as e:
        health_status.status = "unhealthy"
        health_status.services.ollama = f"offline (Error: {str(e)})"

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=json.loads(health_status.model_dump_json()),
        )

    return health_status


@app.post(
    "/sessions",
    tags=["Chat sessions"],
    response_model=SessionCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_chat_session():
    return SessionCreated(session_id=create_session())


@app.get(
    "/sessions/{session_id}",
    tags=["Chat sessions"],
    response_model=list[Message],
)
async def get_chat_session(session_id: str):
    session = get_session(session_id)
    return session.messages


@app.delete(
    "/sessions/{session_id}",
    tags=["Chat sessions"],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_chat_session(session_id: str):
    get_session(session_id)
    del sessions[session_id]


@app.post("/generate", tags=["Text generation"])
async def generate_from_ollama(turn: ChatTurn):
    session = get_session(turn.session_id)

    async def generate_chunks():
        async with session.lock:
            session.messages.append(Message(role=Role.user, content=turn.text))
            overflow = len(session.messages) - settings.max_session_messages
            if overflow > 0:
                del session.messages[:overflow]

            reply = ""
            try:
                stream = await ollama_client.chat(
                    model=settings.ollama_model,
                    messages=[m.model_dump() for m in session.messages],
                    stream=True,
                )
                async for chunk in stream:
                    piece = chunk.message.content
                    reply += piece
                    yield piece
            except Exception as e:
                print(f"Error during generation: {str(e)}")
                yield f"\n[Error: Failed to generate response - {str(e)}]"
                return

            session.messages.append(Message(role=Role.assistant, content=reply))
            session.last_accessed = datetime.now(timezone.utc)

    return StreamingResponse(generate_chunks(), media_type="text/event-stream")
