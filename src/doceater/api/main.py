"""FastAPI application for DocEater."""

import time
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from ..config import get_settings
from .auth import init_auth_config
from .models.responses import ErrorResponse


# Global state for tracking startup time
startup_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("🚀 Starting DocEater API server...")
    
    # Initialize authentication
    settings = get_settings()
    init_auth_config(settings)
    logger.info("🔐 Authentication system initialized")
    
    # TODO: Initialize embedding service
    # TODO: Warm up models if needed
    
    logger.info("✅ DocEater API server started successfully")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down DocEater API server...")
    # TODO: Cleanup resources
    logger.info("✅ DocEater API server shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title="DocEater API",
        description="Multimodal document processing and search API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    
    # Configure CORS
    if settings.cors_origins:
        origins = [origin.strip() for origin in settings.cors_origins.split(",")]
        methods = [method.strip() for method in settings.cors_methods.split(",")]
        headers = [header.strip() for header in settings.cors_headers.split(",")]
        
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=methods,
            allow_headers=headers,
        )
    
    # Add request ID middleware
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        """Add request ID to all requests."""
        import uuid
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Add to response headers
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    
    # Add timing middleware
    @app.middleware("http")
    async def add_timing(request: Request, call_next):
        """Add timing information to responses."""
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response
    
    # Exception handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle validation errors."""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                error="validation_error",
                message="Request validation failed",
                detail=str(exc),
                timestamp=time.time(),
                request_id=getattr(request.state, "request_id", None),
            ).model_dump(),
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle general exceptions."""
        logger.exception(f"Unhandled exception in {request.method} {request.url}")
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="internal_server_error",
                message="An internal server error occurred",
                detail=str(exc) if settings.log_level == "DEBUG" else None,
                timestamp=time.time(),
                request_id=getattr(request.state, "request_id", None),
            ).model_dump(),
        )
    
    # Register routes
    from .routes import health, documents, search, images
    
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(documents.router, prefix="/api/v1", tags=["documents"])
    app.include_router(search.router, prefix="/api/v1", tags=["search"])
    app.include_router(images.router, prefix="/api/v1", tags=["images"])
    
    return app


# Create the app instance
app = create_app()


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint redirect to docs."""
    return {"message": "DocEater API", "docs": "/docs", "health": "/api/v1/health"}


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "doceater.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        reload=settings.api_reload,
        access_log=True,
        log_level=settings.log_level.lower(),
    )
