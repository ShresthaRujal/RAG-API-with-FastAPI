
from config import settings
from repositories.profile_repository import ProfileRepository


class DirectoryService:

    def __init__(self, repository: ProfileRepository):
        self.repository = repository

    def search(self, query: str):

        return self.repository.search_public(
            query=query,
            top_k=settings.TOP_K * 5,
        )
