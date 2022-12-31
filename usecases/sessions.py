import time
from typing import Any, Optional, TypedDict

from fakeredis._server import FakeStrictRedis
from sqlmodel import Session as DatabaseSession

import common
import config
import functions.accounts
import functions.hash
import functions.security
import functions.session
import functions.time
import packets
from enums.actions import ActionType
from enums.game_mode import GameMode
from enums.mods import Mods
from enums.privileges import ServerPrivileges
from packets import Packet
from repositories.accounts import AccountRepo
from repositories.channels import Channel, ChannelRepo
from repositories.sessions import Session, SessionRepo

USER_ID = int


class BrodcastToSessionsResult(TypedDict):
    success: bool


def brodcast_to_sessions(
    data: bytes,
    session_repo: SessionRepo,
    exclude: Optional[list[USER_ID]] = None,
) -> BrodcastToSessionsResult:
    if exclude is None:
        exclude = []

    sessions = session_repo.fetch_all()

    for session in sessions:
        if session["account"]["id"] in exclude:
            continue

        session["packet_queue"] += data

        session_repo.update(session["token"], session)

    return BrodcastToSessionsResult(success=True)


class BrodcastEveryoneToResult(TypedDict):
    success: bool


def brodcast_everyone_to(
    session_token: str,
    session_repo: SessionRepo,
    exclude: Optional[list[USER_ID]] = None,
) -> BrodcastEveryoneToResult:
    if exclude is None:
        exclude = []

    session_wanting_data = session_repo.fetch_one(token=session_token)

    assert session_wanting_data, "this should never happen"  # TODO: handle properly?

    for session in session_repo.fetch_all():
        if session["account"]["id"] in exclude:
            continue

        session_wanting_data["packet_queue"] += packets.pack_osu_session(session)

    session_repo.update(session_token, session_wanting_data)

    return BrodcastEveryoneToResult(success=True)


class LoginResult(TypedDict):
    error_message: Optional[str]
    token: Optional[str]
    packets: Optional[bytes]


async def normal_login(
    user_name: str,
    password_md5: str,
    utc_offset: int,
    account_repo: AccountRepo,
    session_repo: SessionRepo,
    channel_repo: ChannelRepo,
) -> LoginResult:
    ...


#    account = account_repo.fetch_one(user_name=user_name)
#
#    if account is None:
#        return LoginResult(
#            error_message="account doesn't exist",
#            token=None,
#            packets=None,
#        )
#
#    if not functions.security.verify_password(password_md5, account["password_argon2"]):
#        return LoginResult(
#            error_message="password is incorrect",
#            token=None,
#            packets=None,
#        )
#
#    # actual login (try catch?)
#    token = functions.session.generate_token()
#
#    # TODO: channel joining
#
#    session = session_repo.create(
#        token=token,
#        account=account,
#        last_pinged=time.time(),
#        channels_in=[],
#        match=None,
#    )
#
#    account_repo.commit()
#
#    return LoginResult(
#        token=token,
#        packets=packets.login_session(session),
#        error_message=None,
#    )


async def developer_login(
    user_name: str,
    password_md5: str,
    utc_offset: int,
    account_repo: AccountRepo,
    session_repo: SessionRepo,
    channel_repo: ChannelRepo,
) -> LoginResult:
    account = account_repo.fetch_one(user_name=user_name)
    session = session_repo.fetch_one(user_name=user_name)

    if session is not None:
        return LoginResult(
            error_message="User is already logged in",
            token=None,
            packets=None,
        )

    if account is None:
        account = account_repo.create(
            user_id=functions.accounts.generate_user_id(account_repo),
            user_name=user_name,
            email_address="test@test.com",
            password_argon2=functions.hash.encrypt_password_md5(password_md5),
            friends=[],
            country_code=functions.time.country_code_from_utc_offset(utc_offset),
            privileges=ServerPrivileges.Normal,
        )

    # actual login (try catch?)
    token = functions.session.generate_token()

    session = session_repo.create(
        token=token,
        account=account,
        last_pinged=time.time(),
        channels_in=["#osu"],
        match=None,
        utc_offset=utc_offset,
    )

    channels: list[Channel] = []

    for channel_name in session["channels_in"]:
        channel = channel_repo.fetch_one(name=channel_name)
        if channel is None:
            continue

        if not channel["auto_join"]:
            continue

        channels.append(channel)

    login_packets = packets.login_session(session, channels)

    # TODO: handle blocked users
    result = brodcast_to_sessions(
        data=login_packets["user_data"],
        session_repo=session_repo,
        exclude=[session["account"]["id"]],
    )

    # TODO: check if successful

    # TODO: handle blocked users
    result = brodcast_everyone_to(
        session_token=session["token"],
        session_repo=session_repo,
        exclude=[session["account"]["id"]],
    )

    # TODO: check if successful

    account_repo.commit()

    return LoginResult(
        token=token,
        packets=login_packets["login_packets"],
        error_message=None,
    )


async def login(
    user_name: str,
    password_md5: str,
    utc_offset: int,
    database_session: DatabaseSession,
    redis_session: FakeStrictRedis,
) -> LoginResult:
    # validation actual
    account_repo = AccountRepo(database_session)
    session_repo = SessionRepo(redis_session)
    channel_repo = ChannelRepo(redis_session)

    if config.DeveloperSettings.create_account_on_login:
        return await developer_login(
            user_name=user_name,
            password_md5=password_md5,
            utc_offset=utc_offset,
            account_repo=account_repo,
            session_repo=session_repo,
            channel_repo=channel_repo,
        )
    else:
        return await normal_login(  # TODO: finish this
            user_name=user_name,
            password_md5=password_md5,
            utc_offset=utc_offset,
            account_repo=account_repo,
            session_repo=session_repo,
            channel_repo=channel_repo,
        )


class HandlePacketsResult(TypedDict):
    response_packets: bytes


class DataSessions(TypedDict):
    database_session: DatabaseSession
    redis_session: FakeStrictRedis


async def handle_packets(
    token: str,
    parsed_packets: list[Packet],
    database_session: DatabaseSession,
    redis_session: FakeStrictRedis,
) -> HandlePacketsResult:
    account_repo = AccountRepo(database_session)
    session_repo = SessionRepo(redis_session)
    channel_repo = ChannelRepo(redis_session)

    all_data_sessions = DataSessions(
        database_session=database_session,
        redis_session=redis_session,
    )

    session = session_repo.fetch_one(token=token)

    if session is None:
        # player has to be looking for restart if this happens
        return HandlePacketsResult(
            response_packets=(
                packets.notification("restarting server") + packets.system_restart()
            )
        )

    pending_packets = bytearray()

    for packet in parsed_packets:
        if packet.id not in common.packet_handlers:
            print(f"Need to handle: {repr(packet)}")
            continue

        if packet.data:
            args = [token, all_data_sessions, packet.data]
        else:
            args = [token, all_data_sessions]

        updated_session: Optional[Session] = await common.packet_handlers[packet.id](
            *args
        )
        if updated_session is None:
            continue

        if updated_session["packet_queue"]:
            pending_packets += updated_session["packet_queue"].copy()
            updated_session["packet_queue"].clear()

        session_repo.update(token=token, updated_session=updated_session)

    return HandlePacketsResult(
        response_packets=bytes(pending_packets),
    )


def update_status(
    session_token: str,
    status: ActionType,
    status_text: str,
    current_map_id: int,
    current_map_md5: str,
    current_game_mode: GameMode,
    current_mods: Mods,
    redis_session: FakeStrictRedis,
) -> Optional[Session]:
    session_repo = SessionRepo(redis_session)

    session = session_repo.fetch_one(token=session_token)

    if session is None:
        return None

    session["status"] = status
    session["status_text"] = status_text
    session["current_map_id"] = current_map_id
    session["current_map_md5"] = current_map_md5
    session["current_game_mode"] = current_game_mode
    session["current_mods"] = current_mods

    return session


def update_users_stats(
    session_token: str,
    user_ids: list[int],
    redis_session: FakeStrictRedis,
) -> Optional[Session]:
    session_repo = SessionRepo(redis_session)

    session = session_repo.fetch_one(token=session_token)

    if session is None:
        return None

    for other_sessions in session_repo.fetch_many(user_ids=user_ids):
        session["packet_queue"] += packets.pack_osu_session(other_sessions)

    return session
