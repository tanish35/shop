from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routes import router
from config.env import DEBUG
from engine import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    yield
    await db.disconnect()


def init_app():
    app = FastAPI(debug=DEBUG, lifespan=lifespan)

    # app.mount("/static", StaticFiles(directory="static"), name="static")
    app.include_router(router)

    return app


app = init_app()
