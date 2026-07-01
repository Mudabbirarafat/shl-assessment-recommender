from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .schemas import ChatRequest, ChatResponse, HealthResponse
from .dialogue import handle_chat
from .catalog import get_catalog

app = FastAPI(title="SHL Assessment Recommender", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
def root():
    return {
        "service": "SHL Assessment Recommender API",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }

@app.on_event("startup")
def _warm_up():
    # Build the TF-IDF index once at startup so /chat calls stay fast and
    # well within the 30s per-call timeout.
    get_catalog()


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    return handle_chat(request.messages)
