import json
import time
import uuid
from datetime import datetime
from typing import Any, AsyncIterable, Callable, Literal, Optional, TypedDict

import pytz
from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import HTMLResponse
from passlib.hash import argon2
from sqlmodel import Session as DatabaseSession
from sqlmodel import select

import common
import config
import constants
import packets
from database import models as database_models
from enums.presence import PresenceFilter
from enums.privileges import ServerPrivileges
from objects import ClientDetails, LoginData, Session, OsuClient
from packets import ClientPackets

bancho_router = APIRouter(
    tags=["Bancho", "Router"],
)

packet_handlers = {}


async def get_database_session() -> AsyncIterable[DatabaseSession]:
    with DatabaseSession(common.database.engine) as session:
        yield session


def parse_login_data(login_data: bytes) -> LoginData:
    user_name, pass_md5, client_details = login_data.decode().splitlines()

    (
        osu_version,
        utc_offset,
        display_city,
        client_hashes,
        pm_private,
    ) = client_details.split("|")

    return LoginData.from_osu_client_login(
        user_name=user_name,
        pass_md5=pass_md5,
        osu_version=osu_version,
        utc_offset=utc_offset,
        display_city=display_city,
        client_hashes=client_hashes,
        pm_private=pm_private,
    )


async def generate_user_id(database_session: DatabaseSession) -> int:
    query = select(database_models.Account)
    accounts = database_session.exec(query).all()

    if not accounts:
        return 4  # Use 3 for bot account
    else:
        return len(accounts) + 4


async def create_account(
    user_name: str,
    pass_md5: str,
    utc_offset: int,
    client_details: ClientDetails,
    database_session: DatabaseSession,
) -> database_models.Account:
    user_id = await generate_user_id(database_session)

    pass_argon2 = argon2.hash(pass_md5)

    country_code = await get_country_code_from_utc_offset(utc_offset)

    account_model = database_models.Account(
        id=user_id,
        user_name=user_name,
        pass_argon2=pass_argon2,
        friends=json.dumps([]),
        country_code=country_code,
        privileges=ServerPrivileges.Normal,
    )

    database_session.add(account_model)

    database_session.commit()

    client_details_model = database_models.ClientDetail(
        user_id=user_id,
        osu_version=client_details.osu_version,
        osu_path_md5=client_details.osu_path_md5,
        adapters_md5=client_details.adapters_md5,
        uninstall_md5=client_details.uninstall_md5,
        disk_signature_md5=client_details.disk_signature_md5,
        adapters=json.dumps(client_details.adapters),
        country_code=country_code,
        login_date=time.time(),
    )

    database_session.add(client_details_model)

    database_session.commit()

    return account_model


async def get_country_code_from_utc_offset(utc_offset: int) -> str:
    for time_zone in pytz.all_timezones:
        tz = pytz.timezone(time_zone)

        offset = tz.utcoffset(datetime.now()).total_seconds() / 3600

        if offset == utc_offset:
            if tz.zone not in constants.time.time_zone_to_country_code:
                continue

            country_code = constants.time.time_zone_to_country_code[tz.zone].lower()

            if country_code not in constants.time.country_codes_to_osu_code:
                continue
            else:
                return country_code

    return "XX"


class LoginResult(TypedDict):
    packets: bytes
    cho_token: str


async def login_developer_mode(
    user_name: str,
    pass_md5: str,
    utc_offset: int,
    client_details: ClientDetails,
    database_session: DatabaseSession,
) -> LoginResult:
    query = select(database_models.Account).where(
        database_models.Account.user_name == user_name
    )
    account = database_session.exec(query).first()

    if account is None:
        account = await create_account(
            user_name=user_name,
            pass_md5=pass_md5,
            utc_offset=utc_offset,
            client_details=client_details,
            database_session=database_session,
        )

    cho_token = str(uuid.uuid1())

    session = Session(
        account=account.as_account_session(),
        osu_client=OsuClient(
            details=client_details,
        ),
        cho_token=cho_token,
        utc_offset=utc_offset,
        privileges=ServerPrivileges(account.privileges),
        last_pinged=time.time(),
    )

    login_packets = bytearray(packets.user_id(session.account.user_id))

    login_packets += packets.notification(config.InGameSettings.login_message)

    login_packets += packets.protocol_version()
    login_packets += packets.bancho_privileges(
        session.osu_client.server_to_client_privileges(session.privileges)
    )
    login_packets += packets.friends_list(session.account.friends)

    login_packets += packets.menu_icon(
        menu_image=config.InGameSettings.menu_icon,
        redirect_url=config.InGameSettings.redirect_url,
    )

    for channel in common.channels:
        if channel.privileges is None:
            # special case (specifically for #lobby)
            continue

        if not channel.privileges & session.privileges:
            continue

        session.join_channel(channel)

        login_packets += packets.channel_info(
            channel.name, channel.description, channel.player_count
        )

    login_packets += packets.channel_info_end()

    for channel in session.channels_in:
        login_packets += packets.channel_join(channel.name)

    user_data = packets.pack_osu_session(session)
    common.osu_sessions.send_to_all(user_data)

    login_packets += user_data
    login_packets += common.osu_sessions.collect_all_sessions_for(session)

    common.osu_sessions.append(session)

    return LoginResult(
        packets=bytes(login_packets),
        cho_token=cho_token,
    )


async def login(request_body: bytes, database_session: DatabaseSession) -> LoginResult:
    # TODO: finish checks and return proper packet structure
    login_data = parse_login_data(request_body)

    if config.DeveloperSettings.create_account_on_login:
        return await login_developer_mode(
            user_name=login_data.user_name,
            pass_md5=login_data.pass_md5,
            utc_offset=login_data.utc_offset,
            client_details=login_data.client_details,
            database_session=database_session,
        )

    query = select(database_models.Account).where(
        database_models.Account.user_name == login_data.user_name
    )
    account = database_session.exec(query).first()

    if account is None:
        return {
            "packets": (
                packets.user_id(-1) + packets.notification("user doesn't exist")
            ),
            "cho_token": "no",
        }

    if common.osu_sessions.get_from_user_id(account.id):
        return {
            "packets": (
                packets.user_id(-1) + packets.notification("User is already logged in")
            ),
            "cho_token": "no",
        }

    is_correct = argon2.verify(login_data.pass_md5, account.pass_argon2)
    if not is_correct:
        return {
            "packets": (
                packets.user_id(-1) + packets.notification("Password is incorrect")
            ),
            "cho_token": "no",
        }

    breakpoint()


@bancho_router.get("/")
async def bancho_http_handler():
    return HTMLResponse(
        "<br>".join(
            [
                "Welcome to the bancho of all time",
                "",
                f"online users: {len(common.osu_sessions)}",
            ]
        )
    )


@bancho_router.post("/")
async def bancho_handler(
    request: Request,
    osu_token: Optional[str] = Header(None),
    user_agent: Literal["osu!"] = Header(...),
    database_session: DatabaseSession = Depends(get_database_session),
):
    if osu_token is None:
        async with common.locks.LOGIN:
            login_data = await login(
                request_body=await request.body(),
                database_session=database_session,
            )
        return Response(
            content=login_data["packets"],
            headers={
                "cho-token": login_data["cho_token"],
            },
        )

    session = common.osu_sessions.get_from_token(osu_token)

    if session is None:
        return Response(
            packets.system_restart() + packets.notification("restarting server")
        )

    packet_queue = bytearray()

    if session.osu_client.packet_queue:
        packet_queue += session.osu_client.clear_packet_queue()

    client_packets = await request.body()

    for packet in packets.read_packets(client_packets):
        if packet.id not in packet_handlers:
            print(f"Need to handle {packet.name}")
        else:
            args: list[Any] = [session]

            if packet.data is not None:
                args.append(packet.data)

            packet_response = await packet_handlers[packet.id](*args) or b""
            if packet_response is None:
                continue

            packet_queue += packet_response

    return Response(
        bytes(packet_queue),
    )


def packet_handler(packet_id: ClientPackets) -> Callable:
    def inner(func: Callable) -> Callable:
        packet_handlers[packet_id] = func
        return func

    return inner


@packet_handler(ClientPackets.PING)
async def ping(session: Session) -> None:
    return None


@packet_handler(ClientPackets.CHANGE_ACTION)
async def change_action(
    session: Session,
    action: packets.Action,
) -> None:
    session.osu_client.status.action = action.action_type
    session.osu_client.status.info_text = action.info_text
    session.osu_client.status.map_md5 = action.map_md5
    session.osu_client.status.mods = action.mods
    session.osu_client.status.mode = action.mode
    session.osu_client.status.map_id = action.map_id

    common.osu_sessions.send_to_all(
        packets.pack_osu_session(session),
    )

    return None


@packet_handler(ClientPackets.USER_STATS_REQUEST)
async def user_stats_request(
    session: Session,
    user_ids: list[int],
) -> None:
    all_users_stats = bytearray()

    sessions = common.osu_sessions.get_from_user_ids(user_ids)

    if sessions is None:
        return None

    for session in sessions:
        all_users_stats += packets.pack_osu_session_stats(session)

    session.osu_client.packet_queue += all_users_stats

    return None


@packet_handler(ClientPackets.SEND_PUBLIC_MESSAGE)
async def send_public_message(
    session: Session,
    message: packets.Message,
) -> None:
    # TODO: make checks?

    channel_name = message.reciever
    channel = common.channels.get_from_name(channel_name)

    if channel is None:
        print(f"{channel_name} doesn't exist?")
        return

    # TODO: make this betters
    # if message.text.startswith(config.BotSettings.command_prefix):
    #    bot = common.osu_sessions.get_bot()
    #    bot_message = await bot.process_command(message.text, session)
    #    if bot_message is not None:
    #        common.osu_sessions.send_to_all(
    #            packets.send_message(
    #                senders_name=bot.user_name,
    #                message=bot_message,
    #                target_channel_or_user=message.reciever,
    #                sender_user_id=bot.user_id,
    #            )
    #        )

    message_packet = packets.send_message(
        senders_name=session.account.user_name,
        message=message.text,
        target_channel_or_user=message.reciever,
        sender_user_id=session.account.user_id,
    )

    # TODO: check if users blocked you
    common.osu_sessions.send_to_all_but(
        excluded=[session],
        data=message_packet,
    )
    return None


@packet_handler(ClientPackets.SEND_PRIVATE_MESSAGE)
async def send_private_message(session: Session, message: packets.Message) -> None:
    target_session = common.osu_sessions.get_from_user_name(message.reciever)

    if target_session is None:
        session.osu_client.packet_queue += packets.notification(
            f"{message.reciever} isn't online"
        )
        return None

    if target_session.is_bot:
        # TODO: process commands
        return None
    else:
        target_session.osu_client.packet_queue += packets.send_message(
            senders_name=session.account.user_name,
            message=message.text,
            target_channel_or_user=message.reciever,
            sender_user_id=session.account.user_id,
        )


@packet_handler(ClientPackets.RECEIVE_UPDATES)
async def receive_updates(
    session: Session,
    presence_filter: PresenceFilter,
) -> None:
    session.osu_client.presence_filter = presence_filter

    return None


@packet_handler(ClientPackets.REQUEST_STATUS_UPDATE)
async def request_status_update(
    session: Session,
) -> None:

    session.osu_client.packet_queue += packets.pack_osu_session_stats(session)

    return None


@packet_handler(ClientPackets.LOGOUT)
async def logout(
    session: Session,
) -> None:
    if (time.time() - session.last_pinged) < 2:
        return None

    common.osu_sessions.remove(session)

    for channel in common.channels:
        if session not in channel:
            continue

        session.leave_channel(channel)

    for other_session in common.osu_sessions:
        if other_session.account.user_id in other_session.account.friends:
            session.osu_client.packet_queue += packets.logout(
                other_session.account.user_id
            )

    return None


@packet_handler(ClientPackets.CHANNEL_PART)
async def channel_part(session: Session, channel_name: str) -> None:
    channel = common.channels.get_from_name(channel_name)
    if channel is None:
        print(
            f"{session.account.user_name} tried leaving {channel_name} when it doesn't exist?"
        )
        return None

    if session not in channel:
        return None
    else:
        session.leave_channel(channel)

    return None


@packet_handler(ClientPackets.CHANNEL_JOIN)
async def channel_join(session: Session, channel_name: str) -> None:
    channel = common.channels.get_from_name(channel_name)

    if channel is None:
        session.osu_client.packet_queue += packets.notification(
            f"{channel_name} doesn't exist"
        )
        return None

    # TODO: checks for the channel

    if session in channel:
        return None

    session.join_channel(channel)

    return None


@packet_handler(ClientPackets.JOIN_LOBBY)
async def join_lobby(session: Session) -> None:
    lobby_channel = common.channels.get_from_name("#lobby")

    assert lobby_channel, "#lobby was not found"

    if session in lobby_channel:
        return None
    else:
        session.join_channel(lobby_channel)

    return None


@packet_handler(ClientPackets.PART_LOBBY)
async def part_lobby(session: Session) -> None:
    lobby_channel = common.channels.get_from_name("#lobby")

    assert lobby_channel, "#lobby was not found"

    if session not in lobby_channel:
        return None
    else:
        session.leave_channel(lobby_channel)

    return None
