from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
import logging
import sqlite3
import time
import uuid
import os
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

from config import settings
from schemas.profile_schema import ProfileRequest


logger = logging.getLogger(__name__)


class ProfileRepository:
    """
    Stores profile chunks in ChromaDB and keeps the active profile version
    in a SQLite manifest.

    A new profile version is written and verified in ChromaDB before the
    SQLite manifest is switched to that version. Previous versions are kept
    temporarily so that a failed write does not destroy the current profile.

    Note: SQLite and ChromaDB do not share a transaction. This design reduces
    the risk of losing an existing profile, but it is not a distributed
    transaction or a complete multi-process consistency solution.
    """

    def __init__(self) -> None:

        # Resolve the ChromaDB storage directory.
        chroma_path = Path(settings.chroma_path).expanduser().resolve()

        # Create directory if it does not exist.
        chroma_path.mkdir(parents=True, exist_ok=True)

        # Check write permissions.
        if not chroma_path.is_dir():
            raise RuntimeError(
                f"ChromaDB path is not a directory: {chroma_path}"
            )

        if not os.access(chroma_path, os.W_OK):
            raise PermissionError(
                f"No write permission for ChromaDB directory: {chroma_path}"
            )

        self.client = chromadb.PersistentClient(
            path=str(chroma_path)
        )

        self.embedding_function = OllamaEmbeddingFunction(
            url=settings.OLLAMA_URL,
            model_name=settings.EMBEDDING_MODEL,
        )

        self.collection = self.client.get_or_create_collection(
            name=settings.COLLECTION_NAME,
            embedding_function=self.embedding_function,
        )

        # SQLite manifest location.
        self.manifest_path = chroma_path / "profile_manifest.sqlite3"

        self.manifest_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._initialize_manifest()

    # ==================================================
    # SQLITE MANIFEST
    # ==================================================

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.manifest_path),
            timeout=30,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize_manifest(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS profiles (
                                                        user_id TEXT PRIMARY KEY,
                                                        active_version TEXT NOT NULL,
                                                        full_name TEXT NOT NULL,
                                                        is_public INTEGER NOT NULL,
                                                        updated_at TEXT NOT NULL
                )
                """
            )

    def _get_manifest(self, user_id: str) -> sqlite3.Row | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT user_id, active_version, full_name, is_public, updated_at
                FROM profiles
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

        return row

    def _activate_version(
            self,
            user_id: str,
            version: str,
            profile: ProfileRequest,
    ) -> None:
        """
        Atomically switch the SQLite pointer to the new active version.

        BEGIN IMMEDIATE serializes SQLite writers so two activation writes
        cannot modify the manifest at the same time.
        """
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO profiles (
                    user_id,
                    active_version,
                    full_name,
                    is_public,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(user_id)
                DO UPDATE SET
                    active_version = excluded.active_version,
                                           full_name = excluded.full_name,
                                           is_public = excluded.is_public,
                                           updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    version,
                    profile.full_name,
                    int(profile.is_public),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    # ==================================================
    # INTERNAL HELPERS
    # ==================================================

    @staticmethod
    def _split_content(content: str) -> list[str]:
        """Split profile text into non-empty paragraph chunks."""
        return [
            chunk.strip()
            for chunk in content.split("\n\n")
            if chunk.strip()
        ]

    @staticmethod
    def _profile_filter(user_id: str, version: str) -> dict[str, Any]:
        """ChromaDB filter for one exact user/profile version."""
        return {
            "$and": [
                {"user_id": {"$eq": user_id}},
                {"profile_version": {"$eq": version}},
            ]
        }

    def _get_version_chunks(
            self,
            user_id: str,
            version: str,
    ) -> dict[str, Any]:
        return self.collection.get(
            where=self._profile_filter(user_id, version),
            include=["documents", "metadatas"],
        )

    # ==================================================
    # CREATE / UPDATE PROFILE
    # ==================================================

    def save_profile(
            self,
            user_id: str,
            profile: ProfileRequest,
    ) -> dict[str, Any]:
        """
        Create a new profile version or replace the existing active version.

        1. Split the profile into chunks.
        2. Write chunks under a new version ID.
        3. Verify that all chunks were stored.
        4. Switch the active version in SQLite.
        5. Return the active profile.

        Old versions are intentionally retained for later cleanup.
        """
        chunks = self._split_content(profile.content)

        if not chunks:
            raise ValueError("Profile content cannot be empty.")

        version = str(uuid.uuid4())
        ids = [
            f"user_{user_id}_{version}_{index}"
            for index in range(len(chunks))
        ]

        created_at = time.time()
        metadatas = [
            {
                "user_id": user_id,
                "profile_version": version,
                "full_name": profile.full_name,
                "is_public": bool(profile.is_public),
                "chunk_index": index,
                "created_at": created_at,
            }
            for index in range(len(chunks))
        ]

        activated = False

        try:
            # Write the new version without touching the current active one.
            self.collection.add(
                ids=ids,
                documents=chunks,
                metadatas=metadatas,
            )

            # Verify the complete version is present before activation.
            stored = self._get_version_chunks(user_id, version)

            if len(stored.get("ids", [])) != len(chunks):
                raise RuntimeError("Profile storage verification failed.")

            stored_documents = stored.get("documents") or []
            if len(stored_documents) != len(chunks):
                raise RuntimeError("Not all profile documents were stored.")

            # Only now make the new version active.
            self._activate_version(user_id, version, profile)
            activated = True

        except Exception:
            # Never delete the version if SQLite has already activated it.
            if not activated:
                try:
                    self.collection.delete(
                        where=self._profile_filter(user_id, version)
                    )
                except Exception:
                    logger.exception(
                        "Could not clean up failed profile version %s",
                        version,
                    )
            raise

        # This is deliberately outside the try/except above. If reading the
        # newly active profile fails, do not delete its ChromaDB chunks.
        saved_profile = self.get_profile(user_id)

        if saved_profile is None:
            raise RuntimeError(
                "Profile was activated but could not be retrieved."
            )

        return saved_profile

    # ==================================================
    # GET PROFILE
    # ==================================================

    def get_profile(self, user_id: str) -> dict[str, Any] | None:
        """Retrieve the active profile version for a user."""
        manifest = self._get_manifest(user_id)

        if manifest is None:
            return None

        version = manifest["active_version"]
        result = self._get_version_chunks(user_id, version)

        ids = result.get("ids") or []
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []

        if not ids:
            logger.error(
                "Active profile version has no ChromaDB documents: %s",
                user_id,
            )
            raise RuntimeError("Profile data is temporarily unavailable.")

        profile_chunks = sorted(
            zip(documents, metadatas),
            key=lambda item: item[1].get("chunk_index", 0),
        )

        content = "\n\n".join(
            document
            for document, _metadata in profile_chunks
            if document
        )

        return {
            "user_id": user_id,
            "full_name": manifest["full_name"],
            "content": content,
            "is_public": bool(manifest["is_public"]),
        }

    # ==================================================
    # SEARCH USER PROFILE
    # ==================================================

    def search_user(
            self,
            user_id: str,
            question: str,
            top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """
        Search only the active version of one user's profile.

        The active version is read from SQLite. No Collection.count(where=...)
        call is needed; ChromaDB query returns the requested nearest chunks.
        """
        if top_k < 1:
            return []

        manifest = self._get_manifest(user_id)

        if manifest is None:
            return []

        version = manifest["active_version"]

        results = self.collection.query(
            query_texts=[question],
            n_results=top_k,
            where=self._profile_filter(user_id, version),
            include=["documents", "metadatas", "distances"],
        )

        documents = (results.get("documents") or [[]])[0] or []
        metadatas = (results.get("metadatas") or [[]])[0] or []
        distances = (results.get("distances") or [[]])[0] or []

        return [
            {
                "content": document,
                "metadata": metadata,
                "distance": distance,
            }
            for document, metadata, distance in zip(
                documents,
                metadatas,
                distances,
            )
        ]

    # ==================================================
    # SEARCH PUBLIC DIRECTORY
    # ==================================================

    def search_public(
            self,
            query: str,
            top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search only active versions of public profiles.

        Results are grouped by user_id so a profile appears at most once,
        even if multiple chunks from that profile match the query.
        """
        if top_k < 1:
            return []

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT user_id, active_version, full_name
                FROM profiles
                WHERE is_public = 1
                """
            ).fetchall()

        if not rows:
            return []

        active_filters = [
            {
                "$and": [
                    {"user_id": {"$eq": row["user_id"]}},
                    {
                        "profile_version": {
                            "$eq": row["active_version"]
                        }
                    },
                    {"is_public": {"$eq": True}},
                ]
            }
            for row in rows
        ]

        public_filter = {"$or": active_filters}

        # Collection.count(where=...) is not supported by some ChromaDB
        # versions. Collection.get(where=...) is used to determine the number
        # of matching chunks before setting query's n_results.
        matching_chunks = self.collection.get(
            where=public_filter,
            include=["metadatas"],
        )
        total_chunks = len(matching_chunks.get("ids") or [])

        if total_chunks == 0:
            return []

        result = self.collection.query(
            query_texts=[query],
            n_results=min(top_k, total_chunks),
            where=public_filter,
            include=["documents", "metadatas", "distances"],
        )

        profiles: dict[str, dict[str, Any]] = {}

        result_metadatas = (result.get("metadatas") or [[]])[0] or []

        for metadata in result_metadatas:
            user_id = metadata.get("user_id")

            if user_id and user_id not in profiles:
                profiles[user_id] = {
                    "user_id": user_id,
                    "full_name": metadata.get("full_name", ""),
                }

        return list(profiles.values())

    # ==================================================
    # DELETE PROFILE
    # ==================================================

    def delete_profile(self, user_id: str) -> None:
        """
        Remove the profile's active pointer from SQLite.

        ChromaDB chunks are retained temporarily and can be removed by
        cleanup_old_versions after the retention period.
        """
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                DELETE FROM profiles
                WHERE user_id = ?
                """,
                (user_id,),
            )

            if cursor.rowcount == 0:
                raise ValueError(f"Profile not found: {user_id}")

    # ==================================================
    # OLD VERSION CLEANUP
    # ==================================================

    def cleanup_old_versions(
            self,
            user_id: str,
            retention_seconds: int = 86400,
    ) -> int:
        """
        Delete inactive profile versions older than the retention period.

        If the profile was deleted from SQLite, all of its versions are
        considered inactive. Returns the number of versions deleted.

        Run this as a controlled maintenance task, not on every API request.
        """
        if retention_seconds < 0:
            raise ValueError("retention_seconds cannot be negative.")

        manifest = self._get_manifest(user_id)
        active_version = (
            manifest["active_version"]
            if manifest is not None
            else None
        )

        cutoff = time.time() - retention_seconds

        result = self.collection.get(
            where={"user_id": {"$eq": user_id}},
            include=["metadatas"],
        )

        versions_to_delete: set[str] = set()

        for metadata in result.get("metadatas") or []:
            version = metadata.get("profile_version")
            created_at = metadata.get("created_at")

            if not version or created_at is None:
                continue

            if version == active_version:
                continue

            if float(created_at) < cutoff:
                versions_to_delete.add(version)

        for version in versions_to_delete:
            self.collection.delete(
                where=self._profile_filter(user_id, version)
            )

        return len(versions_to_delete)


# ==================================================
# SHARED REPOSITORY INSTANCE
# ==================================================

@lru_cache
def get_profile_repository() -> ProfileRepository:
    """Return one shared repository instance per application process."""
    return ProfileRepository()
