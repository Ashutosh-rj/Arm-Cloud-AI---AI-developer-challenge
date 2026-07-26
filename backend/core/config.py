import os
from typing import Dict, List, Any
from pydantic import BaseModel, Field

class Settings(BaseModel):
    # App Settings
    API_TITLE: str = Field(default_factory=lambda: os.getenv("API_TITLE", "InferaV22 Platform API"))
    API_VERSION: str = Field(default_factory=lambda: os.getenv("API_VERSION", "1.0.0"))
    TAGLINE: str = Field(default_factory=lambda: os.getenv("TAGLINE", "Every Version. Faster. Smarter. Optimized."))
    
    # Network & CORS
    HOST: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    PORT: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: os.getenv("CORS_ORIGINS", "*").split(","))

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
    REDIS_URL: str = Field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379"))
    DATABASE_URL: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/inferav22"))
    QDRANT_URL: str = Field(default_factory=lambda: os.getenv("QDRANT_URL", "http://localhost:6333"))

settings = Settings()
