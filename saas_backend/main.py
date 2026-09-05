from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import api_routes
from .config import get_settings
from .database import init_db
from .plans.catalog import seed_plans
from .database import SessionLocal


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Clinical AI SaaS API",
        version="0.2.0",
        description=(
            "Backend API for clinical RAG SaaS. "
            "Auth, organizations, document ingestion, clinical chat, analytics. "
            "Frontend consumes this API separately."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if api_routes and hasattr(api_routes, "router"):
        app.include_router(api_routes.router, prefix="/api")

    @app.on_event("startup")
    def _startup() -> None:
        init_db()
        db = SessionLocal()
        try:
            seed_plans(db)
        finally:
            db.close()

    @app.get("/health", tags=["system"])
    async def health_check() -> dict:
        return {"status": "ok", "service": "clinical-ai-backend"}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("saas_backend.main:app", host="0.0.0.0", port=8000, reload=True)
