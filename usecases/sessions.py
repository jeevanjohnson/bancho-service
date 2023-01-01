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
import usecases.channels
import usecases.matches
from enums.actions import ActionType
from enums.game_mode import GameMode
from enums.mods import Mods
from enums.multiplayer import SlotStatus, Team, TeamTypes, WinConditions
from enums.presence import PresenceFilter
from enums.privileges import ServerPrivileges
from packets import Packet
from repositories.accounts import AccountRepo
from repositories.channels import Channel, ChannelRepo
from repositories.matches import Match, MatchRepo
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

    if session:
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

        if packet.data is None:
            args = [token, all_data_sessions]
        else:
            args = [token, all_data_sessions, packet.data]

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




def update_session_stats(
    session_token: str,
    redis_session: FakeStrictRedis,
) -> Optional[Session]:
    session_repo = SessionRepo(redis_session)

    session = session_repo.fetch_one(token=session_token)

    if session is None:
        return None

    session["packet_queue"] += packets.pack_osu_session_stats(session)

    return session


def logout(
    session_token: str,
    redis_session: FakeStrictRedis,
) -> Optional[Session]:
    session_repo = SessionRepo(redis_session)

    session = session_repo.fetch_one(token=session_token)

    if session is None:
        return None

    if (time.time() - session["last_pinged"]) < 2:
        return session

    for channel_name in session["channels_in"]:
        results = usecases.channels.remove_session(
            sessions_token=session_token,
            channel_name=channel_name,
            redis_session=redis_session,
        )

        assert results["success"]

        session["channels_in"].remove(channel_name)

    for other_session in session_repo.fetch_all():
        if other_session["token"] == session_token:
            continue

        other_session["packet_queue"] += packets.logout(
            session["account"]["id"],
        )

    session_deleted = session_repo.delete(session_token)

    return session_deleted


def join_channel(
    session_token: str,
    channel_name: str,
    redis_session: FakeStrictRedis,
) -> Optional[Session]:
    session_repo = SessionRepo(redis_session)
    # channel_repo = ChannelRepo(redis_session)

    session = session_repo.fetch_one(token=session_token)

    if session is None:
        return None

    results = usecases.channels.add_session(
        session_token=session_token,
        channel_name=channel_name,
        redis_session=redis_session,
    )

    if not results["success"]:
        return None

    updated_channel = results["updated_channel"]

    assert updated_channel

    session["channels_in"].append(channel_name)

    session["packet_queue"] += packets.join_channel(
        channel_name=updated_channel["name"],
        description=updated_channel["description"],
        player_count=len(updated_channel["sessions_in"]),
    )
    return session


def part_channel(
    session_token: str,
    channel_name: str,
    redis_session: FakeStrictRedis,
) -> Optional[Session]:
    session_repo = SessionRepo(redis_session)

    session = session_repo.fetch_one(token=session_token)

    if session is None:
        return None

    results = usecases.channels.remove_session(
        sessions_token=session_token,
        channel_name=channel_name,
        redis_session=redis_session,
    )

    if not results["success"]:
        return None

    updated_channel = results["updated_channel"]

    assert updated_channel  # this never happens

    session["channels_in"].remove(channel_name)

    session["packet_queue"] += packets.channel_kick(
        channel_name=channel_name,
    )

    for other_session in session_repo.fetch_many(tokens=updated_channel["sessions_in"]):
        other_session["packet_queue"] += packets.channel_info(
            channel_name=updated_channel["name"],
            channel_description=updated_channel["description"],
            channel_player_count=len(updated_channel["sessions_in"]),
        )

        session_repo.update(
            token=other_session["token"],
            updated_session=other_session,
        )

    return session


def update_presence_filter(
    session_token: str,
    presence_filter: PresenceFilter,
    redis_session: FakeStrictRedis,
) -> Optional[Session]:
    session_repo = SessionRepo(redis_session)

    session = session_repo.fetch_one(token=session_token)

    if session is None:
        return None

    session["presence_filter"] = presence_filter

    return session


class SendMessageToResult(TypedDict):
    success: bool


def send_message_to(
    sender_token: str,
    message: str,
    target_user_name: str,  # TODO: support token?
    redis_session: FakeStrictRedis,
) -> SendMessageToResult:
    session_repo = SessionRepo(redis_session)

    sender_session = session_repo.fetch_one(token=sender_token)

    if sender_session is None:
        return SendMessageToResult(success=False)

    target_session = session_repo.fetch_one(user_name=target_user_name)

    if target_session is None:
        return SendMessageToResult(success=False)

    # send private message to target
    target_session["packet_queue"] += packets.send_message(
        senders_name=sender_session["account"]["user_name"],
        message=message,
        target_channel_or_user=target_session["account"]["user_name"],
        sender_user_id=sender_session["account"]["id"],
    )

    updated_target_session = session_repo.update(
        token=target_session["token"],
        updated_session=target_session,
    )

    return SendMessageToResult(
        success=True,
    )


def send_message(
    session_token: str,
    redis_session: FakeStrictRedis,
    message_content: str,
    target: str,
) -> Optional[Session]:
    # handles channel messages and private messages
    session_repo = SessionRepo(redis_session)

    session = session_repo.fetch_one(token=session_token)

    if session is None:
        return None

    if target.startswith("#"):
        # send message to everyone in channel
        results = usecases.channels.send_message(
            sender_token=session_token,
            message=message_content,
            channel_name=target,
            redis_session=redis_session,
            excluded_session_tokens=[session_token],
        )

        if not results["success"]:
            session["packet_queue"] += packets.notification(
                message=f"couldn't send message to {target}"
            )

    else:
        results = send_message_to(
            sender_token=session_token,
            target_user_name=target,
            message=message_content,
            redis_session=redis_session,
        )

        if not results["success"]:
            session["packet_queue"] += packets.notification(
                message="this user is not online.",
            )

    return session

def create_match(
    session_token: str,
    match: packets.Match,
    redis_session: FakeStrictRedis,
) -> Optional[Session]:
    session_repo = SessionRepo(redis_session)

    session = session_repo.fetch_one(token=session_token)

    if session is None:
        return None

    result = usecases.matches.generate_match_id(
        redis_session=redis_session,
    )

    if result["match_id"] > 64:
        session["packet_queue"] += packets.notification(
            message="No slots available for this match."
        )
        session["packet_queue"] += packets.match_join_fail()
        return session

    match_id = result["match_id"]

    results = usecases.matches.create(
        creator_token=session["token"],
        match_id=match_id,
        host_id=match.host_id,
        game_mode=GameMode(match.game_mode),
        mods=Mods(match.mods),
        match_name=match.name,
        win_condition=WinConditions(match.win_condition),
        team_type=TeamTypes(match.team_type),
        current_map_name=match.map_name,
        current_map_id=match.map_id,
        current_map_md5=match.map_md5,
        seed=match.seed,
        redis_session=redis_session,
    )

    if not results["success"]:
        session["packet_queue"] += packets.notification(
            message="error when creating match..."
        )
        session["packet_queue"] += packets.match_join_fail()
        return session

    return results["updated_host_session"]

def change_match_settings(
    session_token: str,
    new_match: packets.Match,
    redis_session: FakeStrictRedis,
) -> Optional[Session]:
    match_repo = MatchRepo(redis_session)
    session_repo = SessionRepo(redis_session)

    session = session_repo.fetch_one(token=session_token)

    if session is None:
        return None

    match = match_repo.fetch_one(match_id=session["match"])

    if match is None:
        return None

    if session["account"]["id"] != match["host_id"]:
        session["packet_queue"] += packets.notification(message="you are not the host!")
        return session

    taken_slots = [
        slot for slot in match["slots"] if slot["status"] & SlotStatus.HAS_PLAYER
    ]

    if match["free_mod"] != new_match.freemods:
        match["free_mod"] = new_match.freemods

        if new_match.freemods:
            # match mods -> active slot mods.
            # TODO: understand this
            for slot in taken_slots:
                slot["mods"] = match["mods"] & ~Mods.SPEED_CHANGING

            match["mods"] &= Mods.SPEED_CHANGING
        else:
            # host mods -> match mods
            host_slot = [
                slot for slot in match["slots"] if slot["user_id"] == match["host_id"]
            ][0]

            match["mods"] &= Mods.SPEED_CHANGING
            match["mods"] |= host_slot["mods"]

            for slot in taken_slots:
                slot["mods"] = Mods.NOMOD

    if new_match.map_id == -1:
        # map is being changed
        for slot in taken_slots:
            if slot["status"] == SlotStatus.READY:
                slot["status"] = SlotStatus.NOT_READY

        match["previous_map_id"] = match["current_map_id"]

        match["current_map_id"] = -1
        match["current_map_md5"] = ""
        match["current_map_name"] = ""
    elif match["current_map_id"] == -1:
        if match["previous_map_id"] != new_match.map_id:
            ...
