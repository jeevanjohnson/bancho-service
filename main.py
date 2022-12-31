"""Bancho Service: Web server that handles c*.ppy.sh requests."""
import redis
import sqlmodel
import uvicorn
from fakeredis._server import FakeStrictRedis
from fastapi import FastAPI
from sqlmodel import create_engine

import common
from database.models import *
from enums.privileges import ServerPrivileges
from repositories.channels import ChannelRepo

# from objects import Bot

app = FastAPI(
    title="Bancho Service for coveri.xyz",
)


def init_app(app: FastAPI) -> FastAPI:
    # from routers.api import api_router
    from routers.cho import bancho_router

    # app.include_router(api_router, prefix="/api/v1")
    app.include_router(bancho_router)

    @app.on_event("startup")
    async def start_up() -> None:
        common.redis = FakeStrictRedis(version=6)  # TODO: user actual redis
        
        common.database = create_engine(url="sqlite:///database.db", echo=True)

        sqlmodel.SQLModel.metadata.create_all(
            common.database.engine,
        )

        # init channels
        # TODO: more channels?
        account_repo = ChannelRepo(common.redis)

        account_repo.create(
            name="#osu",
            description="main osu! channel",
            auto_join=True,
            privileges=ServerPrivileges.Normal,
        )

    return app


app = init_app(app)


def main() -> int:
    uvicorn.run(
        app="main:app",
        host="127.0.0.1",
        port=8003,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
