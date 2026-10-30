
from schemas.profile_schema import ProfileRequest
from repositories.profile_repository import ProfileRepository


class ProfileService:

    def __init__(self, repository: ProfileRepository):
        self.repository = repository

    def create(
            self,
            user_id: str,
            request: ProfileRequest,
    ):
        # Prevent duplicate profiles
        existing_profile = self.repository.get_profile(user_id)

        if existing_profile:
            raise ValueError(
                f"Profile already exists for user: {user_id}"
            )

        return self.repository.save_profile(
            user_id=user_id,
            profile=request,
        )

    def get(self, user_id: str):
        profile = self.repository.get_profile(user_id)

        if not profile:
            raise ValueError(
                f"Profile not found for user: {user_id}"
            )

        return profile

    def update(
            self,
            user_id: str,
            request: ProfileRequest,
    ):
        # Profile must already exist
        existing_profile = self.repository.get_profile(user_id)

        if not existing_profile:
            raise ValueError(
                f"Profile not found for user: {user_id}"
            )

        return self.repository.save_profile(
            user_id=user_id,
            profile=request,
        )

    def delete(self, user_id: str):
        existing_profile = self.repository.get_profile(user_id)

        if not existing_profile:
            raise ValueError(
                f"Profile not found for user: {user_id}"
            )

        self.repository.delete_profile(user_id)

        return {
            "message": "Profile deleted successfully",
            "user_id": user_id,
        }
