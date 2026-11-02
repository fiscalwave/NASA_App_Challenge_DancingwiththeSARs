"""
FastAPI application factory and configuration.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.utils.errors import ApplicationError
from app.utils.logging import setup_logging, get_logger

logger = get_logger(__name__)


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI app
    """
    app = FastAPI(
        title="NISAR Flood & Wetland Monitor",
        description="API for NASA Space Apps Challenge - Interactive Flood & Wetland Change Mapping",
        version="0.1.0",
    )
    
    # Setup logging
    setup_logging()
    logger.info("Initializing NISAR Flood & Wetland Monitor API")
    
    # Configure CORS for frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register exception handlers
    @app.exception_handler(ApplicationError)
    async def application_error_handler(request, exc: ApplicationError):
        return JSONResponse(
            status_code=400,
            content={
                "error": exc.code,
                "message": exc.message,
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc: Exception):
        logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
            }
        )
    
    # Register routes
    from app.api import search, process, export
    
    app.include_router(search.router, prefix="/api/search", tags=["search"])
    app.include_router(process.router, prefix="/api/process", tags=["process"])
    app.include_router(export.router, prefix="/api/export", tags=["export"])
    
    # Health check
    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}
    
    logger.info("FastAPI application initialized successfully")
    return app


app = create_app()
