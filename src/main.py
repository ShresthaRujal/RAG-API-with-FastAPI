from fastapi import FastAPI
from config import settings

# Import route modules to register their endpoints
import routers.profile_routes
import routers.chat_routes
import routers.directory_routes

from routers import api_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)

app.include_router(api_router)


@app.get("/")
def home():
    return {"message": "Personal AI Directory API is running!"}