from routers import api_router

from controllers.profile_controller import (
    create_profile,
    get_profile,
    update_profile,
    delete_profile,
)

api_router.add_api_route(
    "/profiles/{user_id}",
    create_profile,
    methods=["POST"],
    tags=["Profiles"],
)

api_router.add_api_route(
    "/profiles/{user_id}",
    get_profile,
    methods=["GET"],
    tags=["Profiles"],
)

api_router.add_api_route(
    "/profiles/{user_id}",
    update_profile,
    methods=["PUT"],
    tags=["Profiles"],
)

api_router.add_api_route(
    "/profiles/{user_id}",
    delete_profile,
    methods=["DELETE"],
    tags=["Profiles"],
)