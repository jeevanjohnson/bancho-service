from typing import Optional, TypedDict

from fakeredis._server import FakeStrictRedis

import packets
import usecases.channels
from enums.privileges import ServerPrivileges
from repositories.channels import Channel, ChannelRepo
from repositories.sessions import Session, SessionRepo


class RemoveSessionsResult(TypedDict):
    success: bool
    updated_channel: Optional[Channel]


def remove_sessions(
    sessions_tokens: list[str],
    channel_name: str,
    redis_session: FakeStrictRedis,
) -> RemoveSessionsResult:
    channel_repo = ChannelRepo(redis_session)

    channel = channel_repo.fetch_one(name=channel_name)

    if channel is None:
        return RemoveSessionsResult(
            success=False,
            updated_channel=None,
        )

    for token in sessions_tokens:
        channel["sessions_in"].remove(token)

    updated_channel = channel_repo.update(
        name=channel_name,
        updated_channel=channel,
    )

    return RemoveSessionsResult(
        success=True,
        updated_channel=updated_channel,
    )


class RemoveSessionResult(TypedDict):
    success: bool
    updated_channel: Optional[Channel]


def remove_session(
    sessions_token: str,
    channel_name: str,
    redis_session: FakeStrictRedis,
) -> RemoveSessionResult:
    result = remove_sessions(
        sessions_tokens=[sessions_token],
        channel_name=channel_name,
        redis_session=redis_session,
    )

    if not result["success"]:
        return RemoveSessionResult(
            success=False,
            updated_channel=None,
        )

    return RemoveSessionResult(
        success=True,
        updated_channel=result["updated_channel"],
    )


class AddSessionsResult(TypedDict):
    success: bool
    updated_channel: Optional[Channel]


def add_sessions(
    sessions_tokens: list[str],
    channel_name: str,
    redis_session: FakeStrictRedis,
) -> AddSessionsResult:
    channel_repo = ChannelRepo(redis_session)

    channel = channel_repo.fetch_one(name=channel_name)

    if channel is None:
        return AddSessionsResult(
            success=False,
            updated_channel=None,
        )

    for token in sessions_tokens:
        channel["sessions_in"].append(token)

    updated_channel = channel_repo.update(
        name=channel_name,
        updated_channel=channel,
    )

    return AddSessionResult(
        success=True,
        updated_channel=updated_channel,
    )


class AddSessionResult(TypedDict):
    success: bool
    updated_channel: Optional[Channel]


def add_session(
    session_token: str,
    channel_name: str,
    redis_session: FakeStrictRedis,
) -> AddSessionResult:
    result = add_sessions(
        sessions_tokens=[session_token],
        channel_name=channel_name,
        redis_session=redis_session,
    )

    if not result["success"]:
        return AddSessionResult(
            success=False,
            updated_channel=None,
        )

    return AddSessionResult(
        success=True,
        updated_channel=result["updated_channel"],
    )


class SendMessageTypedDict(TypedDict):
    success: bool


def send_message(
    channel_name: str,
    sender_token: str,
    message: str,
    excluded_session_tokens: list[str],
    redis_session: FakeStrictRedis,
) -> SendMessageTypedDict:
    session_repo = SessionRepo(redis_session)
    channel_repo = ChannelRepo(redis_session)

    channel = channel_repo.fetch_one(name=channel_name)

    if channel is None:
        return SendMessageTypedDict(success=False)

    session_tokens_in = channel["sessions_in"]

    session = session_repo.fetch_one(token=sender_token)
    if session is None:
        return SendMessageTypedDict(success=False)

    for other_session in session_repo.fetch_many(tokens=session_tokens_in):
        if other_session["token"] in excluded_session_tokens:
            continue

        other_session["packet_queue"] += packets.send_message(
            senders_name=session["account"]["user_name"],
            message=message,
            target_channel_or_user=channel_name,
            sender_user_id=session["account"]["id"],
        )

        session_repo.update(
            token=other_session["token"],
            updated_session=other_session,
        )

    return SendMessageTypedDict(success=True)


class CreateMatchChatResult(TypedDict):
    updated_session: Optional[Session]
    channel: Optional[Channel]


def create_match_chat(
    match_chat_name: str,
    match_id: int,
    privileges: ServerPrivileges,
    redis_session: FakeStrictRedis,
    creator_token: str,
    joining_sessions: Optional[list[str]] = None,
) -> CreateMatchChatResult:
    session_repo = SessionRepo(redis_session)
    channel_repo = ChannelRepo(redis_session)

    creator_session = session_repo.fetch_one(creator_token)
    if creator_session is None:
        return CreateMatchChatResult(
            updated_session=None,
            channel=None,
        )

    channel = channel_repo.create(
        name=match_chat_name,
        description=f"Mutli match ({match_id})",
        auto_join=False,
        privileges=privileges,  # TODO: custom privs?
    )

    if joining_sessions is not None:
        results = usecases.channels.add_sessions(
            sessions_tokens=joining_sessions,
            channel_name=match_chat_name,
            redis_session=redis_session,
        )

        assert results["updated_channel"]

        for session in session_repo.fetch_many(tokens=joining_sessions):
            session["channels_in"].append(match_chat_name)
            session["packet_queue"] += packets.join_channel(
                channel_name=channel["name"],
                description=channel["description"],
                player_count=len(channel["sessions_in"]),
            )

            session_repo.update(
                token=session["token"],
                updated_session=session,
            )

    results = usecases.channels.add_session(
        session_token=creator_token,
        channel_name=match_chat_name,
        redis_session=redis_session,
    )

    creator_session["channels_in"].append(match_chat_name)
    creator_session["packet_queue"] += packets.join_channel(
        channel_name=channel["name"],
        description=channel["description"],
        player_count=len(channel["sessions_in"]),
    )

    return CreateMatchChatResult(
        updated_session=creator_session,
        channel=channel,
    )
