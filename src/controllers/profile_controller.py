
from fastapi import (
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from pydantic import ValidationError

from schemas.profile_schema import ProfileRequest
from services.profile_service import ProfileService
from repositories.profile_repository import get_profile_repository


MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB


def get_service():
    repository = get_profile_repository()
    return ProfileService(repository)


async def build_profile_request(
        full_name: str,
        is_public: bool,
        file: UploadFile,
) -> ProfileRequest:

    if not file.filename or not file.filename.lower().endswith(".txt"):
        raise HTTPException(
            status_code=400,
            detail="Only .txt files are allowed.",
        )

    content_bytes = await file.read()

    if not content_bytes:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    if len(content_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File size must not exceed 2 MB.",
        )

    try:
        content = content_bytes.decode("utf-8-sig").strip()
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="File must use UTF-8 encoding.",
        )

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file contains no readable text.",
        )

    try:
        return ProfileRequest(
            full_name=full_name,
            content=content,
            is_public=is_public,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(),
        )


# CREATE PROFILE
async def create_profile(
        user_id: str,
        full_name: str = Form(...),
        is_public: bool = Form(False),
        file: UploadFile = File(...),
        service: ProfileService = Depends(get_service),
):
    request = await build_profile_request(
        full_name,
        is_public,
        file,
    )

    try:
        return service.create(user_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


# GET PROFILE
def get_profile(
        user_id: str,
        service: ProfileService = Depends(get_service),
):
    try:
        return service.get(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# UPDATE PROFILE
async def update_profile(
        user_id: str,
        full_name: str = Form(...),
        is_public: bool = Form(False),
        file: UploadFile = File(...),
        service: ProfileService = Depends(get_service),
):
    request = await build_profile_request(
        full_name,
        is_public,
        file,
    )

    try:
        return service.update(user_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# DELETE PROFILE
def delete_profile(
        user_id: str,
        service: ProfileService = Depends(get_service),
):
    try:
        return service.delete(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
