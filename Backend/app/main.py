from fastapi import FastAPI
import logfire
import os
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

load_dotenv()
logfire.configure(token="pylf_v1_us_mW3J9BlPrwfdjGx2Rx7crJxL51n3bvCd6F69rfY6KyVQ")

from app.api.v1.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.limiter import limiter




def create_app() -> FastAPI:
    

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
    
   
    logfire.instrument_fastapi(app)

    # Consistent error envelope for all error types
    register_exception_handlers(app)

    # Routers
    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
