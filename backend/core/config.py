import os
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

class Settings(BaseModel):
    # App Settings
    API_TITLE: str = Field(default_factory=lambda: os.getenv("API_TITLE", "InferaV22 Platform API"))
    API_VERSION: str = Field(default_factory=lambda: os.getenv("API_VERSION", "1.0.0"))
    TAGLINE: str = Field(default_factory=lambda: os.getenv("TAGLINE", "Every Version. Faster. Smarter. Optimized."))
    
    # Network & CORS
    HOST: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    PORT: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","))

    # Cloud Instance Pricing (USD / hr)
    GRAVITON4_HOURLY_COST: float = Field(default_factory=lambda: float(os.getenv("GRAVITON4_HOURLY_COST", "0.46")))
    COBALT100_HOURLY_COST: float = Field(default_factory=lambda: float(os.getenv("COBALT100_HOURLY_COST", "0.48")))
    AXION_HOURLY_COST: float = Field(default_factory=lambda: float(os.getenv("AXION_HOURLY_COST", "0.49")))
    X86_XEON_HOURLY_COST: float = Field(default_factory=lambda: float(os.getenv("X86_XEON_HOURLY_COST", "0.85")))

    # Verification & Public Base URLs
    VERIFY_BASE_URL: str = Field(default_factory=lambda: os.getenv("VERIFY_BASE_URL", "https://verify.inferav22.dev"))
    
    # Defaults
    DEFAULT_QUALITY_FLOOR: float = Field(default_factory=lambda: float(os.getenv("DEFAULT_QUALITY_FLOOR", "0.98")))
    DEFAULT_MODEL_URL: str = Field(default_factory=lambda: os.getenv("DEFAULT_MODEL_URL", "meta-llama/Llama-3.2-3B-Instruct"))
    
    # Persistent Stores
    REDIS_URL: str = Field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    QUEUE_KEY: str = Field(default_factory=lambda: os.getenv("QUEUE_KEY", "inferav22:optimization:queue"))
    DATABASE_URL: str = Field(default_factory=lambda: os.getenv(
        "DATABASE_URL",
        "postgresql://inferav22:inferav22@localhost:5432/inferav22"
    ))
    QDRANT_URL: str = Field(default_factory=lambda: os.getenv("QDRANT_URL", "http://localhost:6333"))

    # JWT
    JWT_SECRET: str = Field(default_factory=lambda: os.getenv("JWT_SECRET", "INSECURE_DEFAULT_CHANGE_IN_PRODUCTION"))
    JWT_ALGORITHM: str = Field(default_factory=lambda: os.getenv("JWT_ALGORITHM", "HS256"))
    JWT_EXPIRE_MINUTES: int = Field(default_factory=lambda: int(os.getenv("JWT_EXPIRE_MINUTES", "10080")))

    # Inference endpoints
    GRAVITON4_INFERENCE_URL: str = Field(default_factory=lambda: os.getenv("GRAVITON4_INFERENCE_URL", ""))
    COBALT100_INFERENCE_URL: str = Field(default_factory=lambda: os.getenv("COBALT100_INFERENCE_URL", ""))
    AXION_INFERENCE_URL: str = Field(default_factory=lambda: os.getenv("AXION_INFERENCE_URL", ""))

    # HuggingFace
    HF_TOKEN: str = Field(default_factory=lambda: os.getenv("HF_TOKEN", ""))

    # Model storage
    MODEL_CACHE_DIR: str = Field(default_factory=lambda: os.getenv("MODEL_CACHE_DIR", "/models/cache"))

    # App
    APP_VERSION: str = Field(default_factory=lambda: os.getenv("APP_VERSION", "0.1.0"))
    ENVIRONMENT: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    WORKER_CONCURRENCY: int = Field(default_factory=lambda: int(os.getenv("WORKER_CONCURRENCY", "4")))

    def get_inference_url(self, cloud: str) -> str:
        """Get the inference URL for a given cloud provider."""
        mapping = {
            "graviton4": self.GRAVITON4_INFERENCE_URL,
            "cobalt100": self.COBALT100_INFERENCE_URL,
            "axion": self.AXION_INFERENCE_URL,
        }
        return mapping.get(cloud.lower(), "")

    def get_cloud_hourly_cost(self, cloud: str) -> float:
        """Get the hourly cost for a given cloud provider."""
        mapping = {
            "graviton4": self.GRAVITON4_HOURLY_COST,
            "cobalt100": self.COBALT100_HOURLY_COST,
            "axion": self.AXION_HOURLY_COST,
            "x86_xeon": self.X86_XEON_HOURLY_COST,
        }
        return mapping.get(cloud.lower(), 0.5)

settings = Settings()
