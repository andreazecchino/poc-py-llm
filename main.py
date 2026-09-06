import json
import logging
import uuid
from asyncio import Lock
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from ollama import AsyncClient
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def create_session(system: str | None = None) -> str:
    session_id = uuid.uuid4().hex
    initial = [Message(role=Role.system, content=system)] if system else []
    sessions[session_id] = SessionData(messages=initial)
    logger.info("session_created", extra={"session_id": session_id})
    return session_id


def get_session(session_id: str) -> SessionData:
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    ttl = timedelta(minutes=settings.session_ttl_minutes)
    if datetime.now(UTC) - session.last_accessed > ttl:
        del sessions[session_id]
        logger.info("session_expired", extra={"session_id": session_id})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    return session


def format_sse(data: dict, event: str) -> str:
    return f"event: {event} data: {json.dumps(data)}\n"


class Settings(BaseSettings):
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "smollm2:360m-instruct-q4_K_M"
    session_ttl_minutes: int = 30
    max_session_messages: int = 50
    log_level: str = "INFO"
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)


class Role(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class Message(BaseModel):
    role: Role
    content: str


class CreateSessionRequest(BaseModel):
    system: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional system prompt to seed the conversation",
    )


class GenerationOptions(BaseModel):
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    top_k: int | None = Field(default=None, ge=1)
    max_tokens: int | None = Field(
        default=None, ge=1, description="Maps to Ollama's num_predict"
    )


class ChatTurn(BaseModel):
    session_id: str
    text: str = Field(
        min_length=1,
        max_length=2000,
        description="Next message in the conversation",
        default="Tell me about your capabilities in one sentence",
    )
    options: GenerationOptions | None = None


class SessionCreated(BaseModel):
    session_id: str


class Services(BaseModel):
    fastapi: str
    ollama: str


class Health(BaseModel):
    status: str
    services: Services


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if (
                key not in logging.LogRecord("", 0, "", 0, "", (), None).__dict__
                and key != "args"
            ):
                payload[key] = value
        return json.dumps(payload)


@dataclass
class SessionData:
    messages: list[Message] = field(default_factory=list)
    last_accessed: datetime = field(default_factory=lambda: datetime.now(UTC))
    lock: Lock = field(default_factory=Lock)


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
handler = logging.StreamHandler()
handler.setFormatter(JsonLogFormatter())
logger = logging.getLogger("poc_py_llm")
logger.addHandler(handler)
logger.setLevel(settings.log_level)
logger.propagate = False
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
        health_status.services.ollama = f"offline (Error: {e!s})"

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
async def create_chat_session(request: CreateSessionRequest = CreateSessionRequest()):
    return SessionCreated(session_id=create_session(system=request.system))


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
    logger.info("session_deleted", extra={"session_id": session_id})


@app.post("/generate", tags=["Text generation"])
async def generate_from_ollama(turn: ChatTurn, request: Request):
    session = get_session(turn.session_id)

    async def generate_chunks():
        async with session.lock:
            session.messages.append(Message(role=Role.user, content=turn.text))
            pinned = (
                1 if session.messages and session.messages[0].role == Role.system else 0
            )
            overflow = len(session.messages) - settings.max_session_messages
            if overflow > 0:
                del session.messages[pinned : pinned + overflow]

            ollama_options = {}
            if turn.options:
                if turn.options.temperature is not None:
                    ollama_options["temperature"] = turn.options.temperature
                if turn.options.top_p is not None:
                    ollama_options["top_p"] = turn.options.top_p
                if turn.options.top_k is not None:
                    ollama_options["top_k"] = turn.options.top_k
                if turn.options.max_tokens is not None:
                    ollama_options["num_predict"] = turn.options.max_tokens

            reply = ""
            try:
                stream = await ollama_client.chat(
                    model=settings.ollama_model,
                    messages=[m.model_dump() for m in session.messages],
                    stream=True,
                    options=ollama_options or None,
                )
                async for chunk in stream:
                    if await request.is_disconnected():
                        logger.info(
                            "client_disconnected",
                            extra={"session_id": turn.session_id},
                        )
                        return
                    piece = chunk.message.content
                    reply += piece
                    yield format_sse({"content": piece}, event="message")
            except Exception as e:
                logger.error(
                    "generation_failed",
                    extra={"session_id": turn.session_id, "error": str(e)},
                )
                yield format_sse({"error": str(e)}, event="error")
                return

            session.messages.append(Message(role=Role.assistant, content=reply))
            session.last_accessed = datetime.now(UTC)
            logger.info(
                "generation_completed",
                extra={"session_id": turn.session_id, "reply_length": len(reply)},
            )
            yield format_sse({}, event="done")

    return StreamingResponse(generate_chunks(), media_type="text/event-stream")
