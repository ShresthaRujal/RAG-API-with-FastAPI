
import ollama

from config import settings
from repositories.profile_repository import ProfileRepository


class ChatService:

    def __init__(self, repository: ProfileRepository):
        self.repository = repository

    def ask(self, user_id: int, question: str):

        # SQLite stores user IDs as strings.
        user_id = str(user_id)

        # Retrieve the complete profile, including full_name.
        profile = self.repository.get_profile(user_id)

        if not profile:
            return {
                "user_id": user_id,
                "question": question,
                "answer": "No profile found for this user.",
                "context_used": [],
            }

        # Retrieve semantically relevant profile chunks.
        search_results = self.repository.search_user(
            user_id=user_id,
            question=question,
            top_k=settings.TOP_K,
        )

        # search_user() returns dictionaries, not strings.
        context_documents = [
            item["content"]
            for item in search_results
            if item.get("content")
        ]

        # If semantic search returns nothing, use the full profile
        # content as a fallback.
        if not context_documents and profile.get("content"):
            context_documents = [profile["content"]]

        # Always include the profile name.
        profile_context = f"""
Full name: {profile["full_name"]}

Profile information:
{" ".join(context_documents)}
"""

        prompt = f"""
You are a personal AI assistant.

You are answering questions about the profile owner.

RULES:
1. Answer using only the provided profile information.
2. The user's full name is explicitly provided. Use it when asked.
3. Do not invent or assume personal information.
4. If information is unavailable, clearly say so.
5. Give direct and concise answers.

PROFILE INFORMATION:
{profile_context}

QUESTION:
{question}

ANSWER:
"""

        response = ollama.chat(
            model=settings.LLM_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            options={
                "temperature": 0,
            },
        )

        return {
            "user_id": user_id,
            "question": question,
            "answer": response["message"]["content"],
            "context_used": context_documents,
        }
