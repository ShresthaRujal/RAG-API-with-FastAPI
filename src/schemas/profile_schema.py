
from pydantic import BaseModel


class ProfileRequest(BaseModel):
    full_name: str
    content: str
    is_public: bool = False


class ProfileResponse(BaseModel):
    user_id: str
    full_name: str
    content: str
    is_public: bool
