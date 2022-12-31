from typing import AsyncIterable, Literal, Optional, TypedDict

from fakeredis._server import FakeStrictRedis
from fastapi import APIRouter, Depends, Header, Request, Response, status
from fastapi.responses import JSONResponse
from sqlmodel import Session as DatabaseSession
from trycast import trycast

import common
import functions.cho
import packets
import usecases.sessions

bancho_router = APIRouter(tags=["Bancho", "Router"])

# EACH function should have only one job it should be doing


async def get_database_session() -> AsyncIterable[DatabaseSession]:
    with DatabaseSession(common.database.engine) as session:
        yield session


async def get_redis_session() -> FakeStrictRedis:
    return common.redis


class LoginResult(TypedDict):
    cho_token: str
    packets: bytes


async def handle_login(
    redis_session: FakeStrictRedis,
    database_session: DatabaseSession,
    login_data: bytes,
) -> LoginResult:
    parsed_login_data = functions.cho.parse_login_data(login_data)

    login_result = await usecases.sessions.login(
        user_name=parsed_login_data["user_name"],
        password_md5=parsed_login_data["password_md5"],
        utc_offset=parsed_login_data["utc_offset"],
        database_session=database_session,
        redis_session=redis_session,
    )

    if login_result["error_message"] is not None:
        error_packets = packets.user_id(-1) + packets.notification(
            message=login_result["error_message"]
        )
        return LoginResult(
            cho_token="error",
            packets=error_packets,
        )

    assert login_result["token"] and login_result["packets"]

    return LoginResult(
        cho_token=login_result["token"],
        packets=login_result["packets"],
    )


class SessionResult(TypedDict):
    packets: bytes


async def handle_session(
    osu_token: str,
    database_session: DatabaseSession,
) -> SessionResult:
    ...


@bancho_router.post("/")
async def bancho_handler(
    request: Request,
    osu_token: Optional[str] = Header(None),
    user_agent: Literal["osu!"] = Header(...),
    database_session: DatabaseSession = Depends(get_database_session),
    redis_session: FakeStrictRedis = Depends(get_redis_session),
):
    # logic
    # check for error
    # fmt data
    # send data
    if osu_token is None:
        data = await handle_login(
            redis_session=redis_session,
            database_session=database_session,
            login_data=await request.body(),
        )
    else:
        data = await handle_session(
            osu_token=osu_token,
            database_session=database_session,
        )

    if validated_data := trycast(LoginResult, data):
        return Response(
            content=validated_data["packets"],
            headers={
                "cho-token": validated_data["cho_token"],
            },
        )
    elif validated_data := trycast(SessionResult, data):
        return Response(
            content=validated_data["packets"],
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": data,
            },
        )
