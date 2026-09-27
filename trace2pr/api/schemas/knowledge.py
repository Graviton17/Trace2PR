from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class PastIncident(BaseModel):
    id: str
    title: str
    resolution_summary: str
    created_at: datetime
    similarity_score: Optional[float] = None

class PastFix(BaseModel):
    id: str
    description: str
    diff_summary: str
    created_at: datetime
    similarity_score: Optional[float] = None

class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    types: List[str] = ["incidents", "fixes"]

class SearchResults(BaseModel):
    incidents: List[PastIncident] = []
    fixes: List[PastFix] = []

class FeedbackRequest(BaseModel):
    item_id: str
    item_type: str
    helpful: bool
    comments: Optional[str] = None

class KBStats(BaseModel):
    total_incidents_indexed: int
    total_fixes_indexed: int
    last_updated: datetime
