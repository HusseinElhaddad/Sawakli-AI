import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sawakli.api.routes import auth, campaigns, data_sources
from sawakli.api.routes.analysis import router as analysis_router
from sawakli.api.routes.jobs import router as jobs_router

app = FastAPI()

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth.router)
app.include_router(campaigns.router)
app.include_router(data_sources.router)
app.include_router(jobs_router, prefix="/api/jobs", tags=["jobs"])
app.include_router(analysis_router, prefix="/api/analysis", tags=["analysis"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Running Command: uv run uvicorn sawakli.api.main:app --reload --port 8000
