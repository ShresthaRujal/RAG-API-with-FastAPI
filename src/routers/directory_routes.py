from routers import api_router
from controllers.directory_controller import search_directory

api_router.add_api_route(
    "/directory/search",
    search_directory,
    methods=["POST"],
    tags=["Directory"]
)