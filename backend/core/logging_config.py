import logging
import os
import structlog

def configure_logging():
    """
    Configure structlog for structured JSON logging.
    Call once at application startup.
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, log_level, logging.INFO)

    # Configure standard library logging
    logging.basicConfig(
        level=numeric_level,
        format="%(message)s",
        handlers=[logging.StreamHandler()]
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Silence noisy libraries
    for noisy_lib in ["uvicorn.access", "asyncpg", "httpx"]:
        logging.getLogger(noisy_lib).setLevel(logging.WARNING)

def bind_run_context(run_id: str, model_url: str = ""):
    """Bind run-specific context to all log records in this async context."""
    structlog.contextvars.bind_contextvars(
        run_id=run_id,
        model_url=model_url[:50] if model_url else "",
    )

def clear_run_context():
    """Clear run context (call after run completes)."""
    structlog.contextvars.clear_contextvars()
