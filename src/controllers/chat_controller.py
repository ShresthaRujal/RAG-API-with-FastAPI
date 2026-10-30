
from fastapi import Depends

from repositories.profile_repository import (
    ProfileRepository,
    get_profile_repository,
)
from services.chat_service import ChatService
from schemas.chat_schema import ChatRequest


def get_service(
        repository: ProfileRepository = Depends(get_profile_repository),
):
    return ChatService(repository)


def ask_question(
        user_id: int,
        request: ChatRequest,
        service: ChatService = Depends(get_service),
):
    return service.ask(user_id, request.question)
