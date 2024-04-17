import asyncio
import atexit
import contextlib
import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from rich import print

from pangloss_core.settings import BaseSettings
from pangloss_core.users import setup_user_routes
from pangloss_core.database import initialise_database_driver

logger = logging.getLogger("uvicorn.info")
RunningBackgroundTasks = []


def get_application(settings: BaseSettings):
    DEVELOPMENT_MODE = "--reload" in sys.argv # Dumb hack!

    from pangloss_core.model_setup.model_manager import ModelManager
    from pangloss_core.api import setup_api_routes
    from pangloss_core.background_tasks import BackgroundTaskRegistry, BackgroundTaskCloseRegistry
    
    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        # Load the ML model
        for task in BackgroundTaskRegistry:
            if not DEVELOPMENT_MODE or task["run_in_dev"]:
            
                running_task = asyncio.create_task(task["function"]())
             
                RunningBackgroundTasks.append(running_task)
            else:
                logger.warning(f"Skipping background task '{task["name"]}' for development mode")
        yield
        
            
        for task in BackgroundTaskCloseRegistry:
            await task()
            
        logging.info("Closing background tasks...")
        for task in RunningBackgroundTasks:
            task.cancel()    
            
        logging.info("Background tasks closed")

    for installed_app in settings.INSTALLED_APPS:
        __import__(f"{installed_app}.models")
        try:
            __import__(f"{installed_app}.background_tasks")
        except ModuleNotFoundError:
            pass
        __import__(installed_app)

    ModelManager.initialise_models(depth=3)
    initialise_database_driver(settings)
    _app = FastAPI(
        title=settings.PROJECT_NAME,
        swagger_ui_parameters={"defaultModelExpandDepth": 1, "deepLinking": True},
        lifespan=lifespan,
    )
    _app = setup_api_routes(_app, settings)
    _app = setup_user_routes(_app, settings)
    _app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    _app.add_middleware(GZipMiddleware, minimum_size=400)
    
    

    return _app


