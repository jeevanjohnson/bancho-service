from typing import Any, AsyncIterable, Callable, Literal, Optional, TypedDict

from fakeredis._server import FakeStrictRedis
from fastapi import APIRouter, Depends, Header, Request, Response, status
from fastapi.responses import JSONResponse
from sqlmodel import Session as DatabaseSession
from trycast import trycast

import common
import functions.cho
import packets
import usecases.sessions
from enums.presence import PresenceFilter
from packets import ClientPackets
from repositories.sessions import Session
from usecases.sessions import DataSessions

bancho_router = APIRouter(tags=["Bancho", "Router"])

# EACH function should have only one job it should be doing
packet_handlers = {}


async def get_database_session() -> AsyncIterable[DatabaseSession]:
    with DatabaseSession(common.database) as session:
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

    if login_result["error_message"]:
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
    response_packets: bytes


async def handle_session(
    token: str,
    raw_packets: bytes,
    database_session: DatabaseSession,
    redis_session: FakeStrictRedis,
) -> SessionResult:
    parsed_packets = packets.read_packets(raw_packets)

    result = await usecases.sessions.handle_packets(
        token=token,
        parsed_packets=parsed_packets,
        database_session=database_session,
        redis_session=redis_session,
    )

    return SessionResult(
        response_packets=result["response_packets"],
    )


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
            token=osu_token,
            raw_packets=await request.body(),
            database_session=database_session,
            redis_session=redis_session,
        )

    # TODO: not sure about this anymore
    if validated_data := trycast(LoginResult, data):
        return Response(
            content=validated_data["packets"],
            headers={
                "cho-token": validated_data["cho_token"],
            },
        )
    elif validated_data := trycast(SessionResult, data):
        return Response(
            content=validated_data["response_packets"],
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": data,
            },
        )


def packet_handler(packet_id: ClientPackets) -> Callable:
    def inner(func: Callable) -> Callable:
        common.packet_handlers[packet_id] = func
        return func

    return inner


# packet_handlers can return either an updated session or nothing
# each packet handler takes the identifier of the session (token)
# and the avaliable data sessions

# TODO: errors?


@packet_handler(ClientPackets.PING)
async def ping(
    token: str,
    data_sessions: DataSessions,
) -> Optional[Session]:
    return None


@packet_handler(ClientPackets.CHANGE_ACTION)
async def change_action(
    token: str,
    data_sessions: DataSessions,
    action: packets.Action,
) -> Optional[Session]:
    updated_session = usecases.sessions.update_status(
        session_token=token,
        status=action.action_type,
        status_text=action.info_text,
        current_map_id=action.map_id,
        current_map_md5=action.map_md5,
        current_game_mode=action.game_mode,
        current_mods=action.mods,
        redis_session=data_sessions["redis_session"],
    )

    if updated_session is None:
        return None

    return updated_session


@packet_handler(ClientPackets.USER_STATS_REQUEST)
async def user_stats_request(
    token: str,
    data_sessions: DataSessions,
    user_ids: list[int],
) -> Optional[Session]:
    updated_session = usecases.sessions.update_users_stats(
        session_token=token,
        redis_session=data_sessions["redis_session"],
        user_ids=user_ids,
    )

    if updated_session is None:
        return None

    return updated_session


@packet_handler(ClientPackets.SEND_PUBLIC_MESSAGE)
async def send_public_message(
    token: str,
    data_sessions: DataSessions,
    message: packets.Message,
) -> Optional[Session]:
    updated_session = usecases.sessions.send_message(
        session_token=token,
        redis_session=data_sessions["redis_session"],
        message_content=message.text,
        target=message.reciever,
    )

    if updated_session is None:
        return None

    return updated_session


@packet_handler(ClientPackets.SEND_PRIVATE_MESSAGE)
async def send_private_message(
    token: str,
    data_sessions: DataSessions,
    message: packets.Message,
) -> Optional[Session]:
    updated_session = usecases.sessions.send_message(
        session_token=token,
        redis_session=data_sessions["redis_session"],
        message_content=message.text,
        target=message.reciever,
    )

    if updated_session is None:
        return None

    return updated_session


@packet_handler(ClientPackets.JOIN_LOBBY)
async def join_lobby(
    token: str,
    data_sessions: DataSessions,
) -> Optional[Session]:
    updated_session = usecases.sessions.join_lobby(
        session_token=token,
        redis_session=data_sessions["redis_session"],
    )

    if updated_session is None:
        return None

    return updated_session


@packet_handler(ClientPackets.PART_LOBBY)
async def part_lobby(
    token: str,
    data_sessions: DataSessions,
) -> Optional[Session]:
    updated_session = usecases.sessions.part_lobby(
        session_token=token,
        redis_session=data_sessions["redis_session"],
    )

    if updated_session is None:
        return None

    return updated_session


@packet_handler(ClientPackets.CHANNEL_JOIN)
async def channel_join(
    token: str,
    data_sessions: DataSessions,
    channel_name: str,
) -> Optional[Session]:
    updated_session = usecases.sessions.join_channel(
        session_token=token,
        channel_name=channel_name,
        redis_session=data_sessions["redis_session"],
    )

    if updated_session is None:
        return None

    return updated_session


@packet_handler(ClientPackets.CHANNEL_PART)
async def part_channel(
    token: str,
    data_sessions: DataSessions,
    channel_name: str,
) -> Optional[Session]:
    updated_session = usecases.sessions.part_channel(
        session_token=token,
        channel_name=channel_name,
        redis_session=data_sessions["redis_session"],
    )

    if updated_session is None:
        return None

    return updated_session


@packet_handler(ClientPackets.RECEIVE_UPDATES)
async def receive_updates(
    token: str,
    data_sessions: DataSessions,
    presence_filter: PresenceFilter,
) -> Optional[Session]:
    updated_session = usecases.sessions.update_presence_filter(
        session_token=token,
        presence_filter=presence_filter,
        redis_session=data_sessions["redis_session"],
    )

    if updated_session is None:
        return None

    return updated_session


@packet_handler(ClientPackets.REQUEST_STATUS_UPDATE)
async def request_status_update(
    token: str,
    data_sessions: DataSessions,
) -> Optional[Session]:
    updated_session = usecases.sessions.update_session_stats(
        session_token=token,
        redis_session=data_sessions["redis_session"],
    )

    if updated_session is None:
        return None

    return updated_session


@packet_handler(ClientPackets.LOGOUT)
async def logout(
    token: str,
    data_sessions: DataSessions,
) -> Optional[Session]:
    updated_session = usecases.sessions.logout(
        session_token=token,
        redis_session=data_sessions["redis_session"],
    )

    if updated_session is None:
        return None

    return updated_session


@packet_handler(ClientPackets.CREATE_MATCH)
async def create_match(
    token: str,
    data_sessions: DataSessions,
    match: packets.Match,
) -> Optional[Session]:
    updated_session = usecases.sessions.create_match(
        session_token=token,
        redis_session=data_sessions["redis_session"],
        match=match,
    )

    if updated_session is None:
        return None

    return updated_session


@packet_handler(ClientPackets.MATCH_CHANGE_SETTINGS)
async def match_change_settings(
    token: str,
    data_sessions: DataSessions,
    new_match: packets.Match,
) -> Optional[Session]:
    updated_session = usecases.sessions.change_match_settings(
        session_token=token,
        redis_session=data_sessions["redis_session"],
        new_match=new_match,
    )

    if updated_session is None:
        return None

    return updated_session
