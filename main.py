import json
from fastapi import FastAPI, status, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel, Field
from ollama import AsyncClient


class Settings(BaseSettings):
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "smollm2:360m-instruct-q4_K_M"
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)


class Prompt(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=2000,
        description="Prompt for text generation",
        default="Tell me about your capabilities in one sentence",
    )


class Services(BaseModel):
    fastapi: str
    ollama: str


class Health(BaseModel):
    status: str
    services: Services


tags_metadata = [
    {
        "name": "Health check",
        "description": "Verify if all services are online",
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


@app.post("/generate", tags=["Text generation"])
async def generate_from_ollama(
    prompt: Prompt,
):
    async def generate_chunks():
        stream = await ollama_client.generate(
            model=settings.ollama_model,
            prompt=prompt.text,
            stream=True,
            # system=
        )
        async for chunk in stream:
            # print(chunk.response, end="", flush=True)
            yield chunk.response

    return StreamingResponse(generate_chunks(), media_type="text/event-stream")
