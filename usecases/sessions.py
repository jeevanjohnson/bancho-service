from typing import Optional, TypedDict

from fakeredis._server import FakeStrictRedis
from sqlmodel import Session as DatabaseSession

import config
import functions.accounts
import functions.hash
import functions.security
import functions.session
import functions.time
import packets
from repositories.accounts import AccountRepo
from repositories.sessions import SessionRepo
from repositories.channels import ChannelRepo, Channel
from enums.privileges import ServerPrivileges
import time


class LoginResult(TypedDict):
    error_message: Optional[str]
    token: Optional[str]
    packets: Optional[bytes]


USER_ID = int


class BrodcastToSessionsResult(TypedDict):
    succes: bool


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

    return BrodcastToSessionsResult(succes=True)


class BrodcastEveryoneToResult(TypedDict):
    succes: bool


def brodcast_everyone_to(
    session_token: str,
    session_repo: SessionRepo,
    exclude: Optional[list[USER_ID]] = None,
) -> BrodcastEveryoneToResult:
    if exclude is None:
        exclude = []

    session_wanting_data = session_repo.fetch_one(session_token)

    assert session_wanting_data, "this should never happen"  # TODO: handle properly?

    for session in session_repo.fetch_all():
        if session["account"]["id"] in exclude:
            continue

        session_wanting_data["packet_queue"] += packets.pack_osu_session(session)

    session_repo.update(session_token, session_wanting_data)

    return BrodcastEveryoneToResult(succes=True)


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
