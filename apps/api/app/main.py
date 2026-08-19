from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import actions, assistant, auth, health, problems, retros, trends, weekly_reviews

app = FastAPI(title="RetroFlow API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(retros.router, prefix="/api/v1")
app.include_router(actions.router, prefix="/api/v1")
app.include_router(problems.router, prefix="/api/v1")
app.include_router(trends.router, prefix="/api/v1")
app.include_router(assistant.router, prefix="/api/v1")
app.include_router(weekly_reviews.router, prefix="/api/v1")
