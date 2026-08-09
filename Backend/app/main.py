from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.utils.logging import configure_logging, RequestLoggingMiddleware


from app.api.v1.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.limiter import limiter




def create_app() -> FastAPI:

    configure_logging(debug=settings.DEBUG)

    app = FastAPI(
        title=settings.APP_NAME,
        description="Backend foundation for an Agentic Recommendation System.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging
    app.add_middleware(RequestLoggingMiddleware)

    # Consistent error envelope for all error types
    register_exception_handlers(app)

    # Routers
    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()

