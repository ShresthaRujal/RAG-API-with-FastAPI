
from pydantic import BaseModel


class DirectorySearchRequest(BaseModel):
    query: str


class DirectoryProfileResponse(BaseModel):
    user_id: int
    full_name: str
    headline: str
