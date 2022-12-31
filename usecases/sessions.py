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
    redis_connection: FakeStrictRedis,
    exclude: Optional[list[USER_ID]] = None,
) -> BrodcastToSessionsResult:
    session_repo = SessionRepo(redis_connection)

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
    redis_connection: FakeStrictRedis,
    exclude: Optional[list[USER_ID]] = None,
) -> BrodcastEveryoneToResult:
    session_repo = SessionRepo(redis_connection)

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
    database_session: DatabaseSession,
    redis_session: FakeStrictRedis,
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
    database_session: DatabaseSession,
    redis_session: FakeStrictRedis,
) -> LoginResult:
    account_repo = AccountRepo(database_session)
    session_repo = SessionRepo(redis_session)
    channel_repo = ChannelRepo(redis_session)

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
        redis_connection=redis_session,
        exclude=[session["account"]["id"]],
    )

    # TODO: check if successful

    # TODO: handle blocked users
    result = brodcast_everyone_to(
        session_token=session["token"],
        redis_connection=redis_session,
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
    if config.DeveloperSettings.create_account_on_login:
        return await developer_login(
            user_name=user_name,
            password_md5=password_md5,
            utc_offset=utc_offset,
            database_session=database_session,
            redis_session=redis_session,
        )
    else:
        return await normal_login(  # TODO: finish this
            user_name=user_name,
            password_md5=password_md5,
            utc_offset=utc_offset,
            database_session=database_session,
            redis_session=redis_session,
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


def join_lobby(
    session_token: str,
    redis_session: FakeStrictRedis,
) -> Optional[Session]:
    session_repo = SessionRepo(redis_session)

    session = session_repo.fetch_one(token=session_token)

    if session is None:
        return None

    session["in_lobby"] = True

    # TODO: see matches

    return session


def part_lobby(
    session_token: str,
    redis_session: FakeStrictRedis,
) -> Optional[Session]:
    session_repo = SessionRepo(redis_session)

    session = session_repo.fetch_one(token=session_token)

    if session is None:
        return None

    session["in_lobby"] = False

    return session


def join_channel(
    session_token: str,
    channel_name: str,
    redis_session: FakeStrictRedis,
) -> Optional[Session]:
    session_repo = SessionRepo(redis_session)
    channel_repo = ChannelRepo(redis_session)

    session = session_repo.fetch_one(token=session_token)

    if session is None:
        return None

    channel = channel_repo.fetch_one(name=channel_name)

    if channel is None:
        return None

    channel["sessions_in"].append(session_token)
    session["channels_in"].append(channel_name)

    channel_packets = packets.channel_info(
        channel_name=channel["name"],
        channel_description=channel["description"],
        channel_player_count=len(channel["sessions_in"]),
    )
    channel_packets += packets.channel_info_end()
    channel_packets += packets.channel_join(channel["name"])

    session["packet_queue"] += channel_packets

    channel_repo.update(
        name=channel["name"],
        updated_channel=channel,
    )

    return session


def part_channel(
    session_token: str,
    channel_name: str,
    redis_session: FakeStrictRedis,
) -> Optional[Session]:
    session_repo = SessionRepo(redis_session)
    channel_repo = ChannelRepo(redis_session)

    session = session_repo.fetch_one(token=session_token)

    if session is None:
        return None

    channel = channel_repo.fetch_one(name=channel_name)

    if channel is None:
        return None

    channel["sessions_in"].remove(session_token)
    session["channels_in"].remove(channel_name)

    session["packet_queue"] += packets.channel_kick(
        channel_name=channel_name,
    )

    channel_repo.update(
        name=channel["name"],
        updated_channel=channel,
    )

    return session


def send_message(
    session_token: str,
    redis_session: FakeStrictRedis,
    message_content: str,
    target: str,
) -> Optional[Session]:
    # handles channel messages and private messages
    session_repo = SessionRepo(redis_session)
    channel_repo = ChannelRepo(redis_session)

    session = session_repo.fetch_one(token=session_token)

    if session is None:
        return None

    if target.startswith("#"):
        # send message to everyone in channel
        channel = channel_repo.fetch_one(name=target)
        assert channel, "TODO: handle this properly"

        session_tokens_in = channel["sessions_in"]

        # remove sender's session token so message won't be sent twice
        session_tokens_in.remove(session_token)

        for other_session in session_repo.fetch_many(tokens=session_tokens_in):
            other_session["packet_queue"] += packets.send_message(
                senders_name=session["account"]["user_name"],
                message=message_content,
                target_channel_or_user=target,
                sender_user_id=session["account"]["id"],
            )

            session_repo.update(
                token=other_session["token"],
                updated_session=other_session,
            )
    else:
        target_session = session_repo.fetch_one(user_name=target)
        assert target_session, "TODO: handle this properly"
        # send private message to target
        target_session["packet_queue"] += packets.send_message(
            senders_name=session["account"]["user_name"],
            message=message_content,
            target_channel_or_user=target,
            sender_user_id=session["account"]["id"],
        )

        session_repo.update(
            token=target_session["token"],
            updated_session=target_session,
        )

    return session
