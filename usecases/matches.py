from typing import Optional, TypedDict

from fakeredis._server import FakeStrictRedis

import packets
import usecases.channels
from enums.game_mode import GameMode
from enums.mods import Mods
from enums.multiplayer import SlotStatus, Team, TeamTypes, WinConditions
from enums.privileges import ServerPrivileges
from repositories.channels import ChannelRepo
from repositories.matches import MatchRepo
from repositories.sessions import Session, SessionRepo


class GenerateMatchIdResult(TypedDict):
    match_id: int


def generate_match_id(
    redis_session: FakeStrictRedis,
) -> GenerateMatchIdResult:
    match_repo = MatchRepo(redis_session)

    return GenerateMatchIdResult(
        match_id=len(match_repo.fetch_all()) + 1,
    )


class CreateResult(TypedDict):
    success: bool
    updated_host_session: Optional[Session]


def create(
    creator_token: str,
    match_id: int,
    host_id: int,
    game_mode: GameMode,
    mods: Mods,
    match_name: str,
    win_condition: WinConditions,
    team_type: TeamTypes,
    current_map_name: str,
    current_map_id: int,
    current_map_md5: str,
    seed: int,
    redis_session: FakeStrictRedis,
) -> CreateResult:
    session_repo = SessionRepo(redis_session)
    match_repo = MatchRepo(redis_session)

    creator_session = session_repo.fetch_one(token=creator_token)
    if creator_session is None:
        return CreateResult(
            success=False,
            updated_host_session=None,
        )

    server_match = match_repo.create(
        match_id=match_id,
        host_id=host_id,
        in_progress=False,
        free_mod=False,
        game_mode=game_mode,
        mods=mods,
        match_name=match_name,
        win_condition=win_condition,
        team_type=team_type,
        current_map_name=current_map_name,
        current_map_id=current_map_id,
        current_map_md5=current_map_md5,
        seed=seed,
    )

    results = usecases.channels.create_match_chat(
        match_chat_name=server_match["channel_name"],
        match_id=match_id,
        privileges=ServerPrivileges.Normal,
        redis_session=redis_session,
        creator_token=creator_token,
        joining_sessions=None,
    )

    if results["updated_session"]:
        creator_session = results["updated_session"]
    else:
        breakpoint(print("shouldnt happen"))

    # TODO: there is an issue were when i leave #lobby it also leaves the multi-channel
    # leave lobby channel

    # have the session join the multi
    creator_session["match"] = server_match["match_id"]

    # update first slot for our session
    slot = server_match["slots"][0]
    slot["user_id"] = creator_session["account"]["id"]
    slot["mods"] = Mods(server_match["mods"])
    slot["status"] = SlotStatus.NOT_READY
    slot["team"] = Team.NEUTRAL

    updated_match = match_repo.update(
        match_id=match_id,
        updated_match=server_match,
    )

    creator_session["packet_queue"] += packets.match_join_sucess(
        match=updated_match,
        send_password=True,  # TODO: what is this
    )

    return CreateResult(
        success=True,
        updated_host_session=creator_session,
    )
