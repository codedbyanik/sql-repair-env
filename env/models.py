from pydantic import BaseModel
from typing import Optional, Any

class Observation(BaseModel):
    broken_query: str
    db_schema: str
    difficulty: str   # ✅ REQUIRED
    result: Optional[Any] = None
    error: Optional[str] = None

class Action(BaseModel):
    query: str