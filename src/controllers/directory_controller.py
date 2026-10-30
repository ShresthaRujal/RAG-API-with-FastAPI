
from fastapi import Depends

from repositories.profile_repository import (
    ProfileRepository,
    get_profile_repository,
)
from services.directory_service import DirectoryService
from schemas.directory_schema import DirectorySearchRequest


def get_service(
    repository: ProfileRepository = Depends(get_profile_repository),
):
    return DirectoryService(repository)


def search_directory(
    request: DirectorySearchRequest,
    service: DirectoryService = Depends(get_service),
):
    return service.search(request.query)
