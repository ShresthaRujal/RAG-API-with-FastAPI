from routers import api_router
from controllers.chat_controller import ask_question

api_router.add_api_route(
    "/chat/{user_id}/ask",
    ask_question,
    methods=["POST"],
    tags=["Chat"]
)