from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime, timezone

class EventData(BaseModel):
    benchmark_results: Optional[list] = []
    certificate: Optional[Dict[str, Any]] = None
    quality_reports: Optional[list] = []

class CanonicalEvent(BaseModel):
    version: str = "1"
    event: str
    run_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    phase: str
    status: Literal["running", "completed", "failed", "queued"] = "running"
    data: EventData = Field(default_factory=EventData)
    error: Optional[str] = None
