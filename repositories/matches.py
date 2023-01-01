import json
from typing import Optional, TypedDict

from fakeredis._server import FakeStrictRedis

from enums.game_mode import GameMode
from enums.mods import Mods
from enums.multiplayer import SlotStatus, Team, TeamTypes, WinConditions

# TODO: should a dict never contain another dict?
# TODO: should repos never have to import each other?


class Slot(TypedDict):
    user_id: Optional[int]
    mods: Mods
    status: SlotStatus
    team: Team


class SlotModel(TypedDict):
    user_id: Optional[int]
    mods: int
    status: int
    team: int


class Match(TypedDict):
    # "x" is what the function returns
    match_id: int
    host_id: int
    channel_name: str

    password: Optional[str]  # TODO: needs to be optional?
    in_progress: bool
    free_mod: bool
    game_mode: GameMode
    mods: Mods
    match_name: str
    win_condition: WinConditions
    team_type: TeamTypes
    seed: int

    current_map_name: str
    current_map_id: int
    current_map_md5: str

    previous_map_name: Optional[str]
    previous_map_id: Optional[int]
    previous_map_md5: Optional[str]

    slots: list[Slot]


class MatchModel(TypedDict):
    # "xModel" is what goes into the database
    match_id: int
    host_id: int
    channel_name: str

    password: Optional[str]  # TODO: needs to be optional?
    in_progress: bool
    free_mod: bool
    game_mode: int
    mods: int
    match_name: str
    win_condition: int
    team_type: int
    seed: int

    current_map_name: str
    current_map_id: int
    current_map_md5: str

    previous_map_name: Optional[str]
    previous_map_id: Optional[int]
    previous_map_md5: Optional[str]

    slots: list[SlotModel]


class MatchRepo:
    # fetch_one
    # fetch_many
    # fetch_all
    # delete
    # update
    # create
    # commit
    def __init__(self, redis_connection: FakeStrictRedis) -> None:
        self.redis_connection = redis_connection

        # TODO: self.key = "bancho:matches:{match_id}" ?

    def fetch_one(
        self,
        match_id: Optional[int] = None,
    ) -> Optional[Match]:
        if match_id is not None:
            raw_match = self.redis_connection.get(f"bancho:matches:{match_id}")
            if raw_match is None:
                return None

            match_model: MatchModel = json.loads(raw_match)
        else:
            return None

        slots = [
            Slot(
                user_id=slot_model["user_id"],
                mods=Mods(slot_model["mods"]),
                status=SlotStatus(slot_model["status"]),
                team=Team(slot_model["team"]),
            )
            for slot_model in match_model["slots"]
        ]

        return Match(
            match_id=match_model["match_id"],
            host_id=match_model["host_id"],
            password=match_model["password"],
            in_progress=match_model["in_progress"],
            free_mod=match_model["free_mod"],
            game_mode=GameMode(match_model["game_mode"]),
            mods=Mods(match_model["mods"]),
            match_name=match_model["match_name"],
            win_condition=WinConditions(match_model["win_condition"]),
            team_type=TeamTypes(match_model["team_type"]),
            current_map_name=match_model["current_map_name"],
            current_map_id=match_model["current_map_id"],
            current_map_md5=match_model["current_map_md5"],
            previous_map_name=match_model["previous_map_name"],
            previous_map_id=match_model["previous_map_id"],
            previous_map_md5=match_model["previous_map_md5"],
            slots=slots,
            channel_name=match_model["channel_name"],
            seed=match_model["seed"],
        )

    def update(
        self,
        match_id: int,
        updated_match: Match,
    ) -> Match:

        slot_models = [
            SlotModel(
                user_id=slot["user_id"],
                mods=int(slot["mods"]),
                status=int(slot["status"]),
                team=int(slot["team"]),
            )
            for slot in updated_match["slots"]
        ]
        match_model = MatchModel(
            match_id=updated_match["match_id"],
            host_id=updated_match["host_id"],
            password=updated_match["password"],
            in_progress=updated_match["in_progress"],
            free_mod=updated_match["free_mod"],
            game_mode=updated_match["game_mode"],
            mods=updated_match["mods"],
            match_name=updated_match["match_name"],
            win_condition=updated_match["win_condition"],
            team_type=updated_match["team_type"],
            current_map_name=updated_match["current_map_name"],
            current_map_id=updated_match["current_map_id"],
            current_map_md5=updated_match["current_map_md5"],
            previous_map_name=updated_match["previous_map_name"],
            previous_map_id=updated_match["previous_map_id"],
            previous_map_md5=updated_match["previous_map_md5"],
            slots=slot_models,
            channel_name=updated_match["channel_name"],
            seed=updated_match["seed"],
        )

        self.redis_connection.set(
            f"bancho:matches:{match_id}",
            json.dumps(match_model),
        )

        return updated_match

    def create(
        self,
        match_id: int,
        host_id: int,
        in_progress: bool,
        free_mod: bool,
        game_mode: GameMode,
        mods: Mods,
        match_name: str,
        win_condition: WinConditions,
        team_type: TeamTypes,
        current_map_name: str,
        current_map_id: int,
        current_map_md5: str,
        seed: int,
        previous_map_name: Optional[str] = None,
        previous_map_id: Optional[int] = None,
        previous_map_md5: Optional[str] = None,
        password: Optional[str] = None,
        # TODO: slots parameter?
    ) -> Match:
        slots = [
            Slot(
                user_id=None,
                mods=mods,
                status=SlotStatus.OPEN,
                team=Team.NEUTRAL,
            )
            for _ in range(16)
        ]

        match = Match(
            match_id=match_id,
            host_id=host_id,
            password=password,
            in_progress=in_progress,
            free_mod=free_mod,
            game_mode=game_mode,
            mods=mods,
            match_name=match_name,
            win_condition=win_condition,
            team_type=team_type,
            current_map_name=current_map_name,
            current_map_id=current_map_id,
            current_map_md5=current_map_md5,
            previous_map_name=previous_map_name,
            previous_map_id=previous_map_id,
            previous_map_md5=previous_map_md5,
            slots=slots,
            channel_name=f"#multi_{match_id}",
            seed=seed,
        )

        slot_models = [
            SlotModel(
                user_id=slot["user_id"],
                mods=int(slot["mods"]),
                status=int(slot["status"]),
                team=int(slot["team"]),
            )
            for slot in slots
        ]

        match_model = MatchModel(
            match_id=match["match_id"],
            host_id=match["host_id"],
            password=match["password"],
            in_progress=match["in_progress"],
            free_mod=match["free_mod"],
            game_mode=match["game_mode"],
            mods=match["mods"],
            match_name=match["match_name"],
            win_condition=match["win_condition"],
            team_type=match["team_type"],
            current_map_name=match["current_map_name"],
            current_map_id=match["current_map_id"],
            current_map_md5=match["current_map_md5"],
            previous_map_name=match["previous_map_name"],
            previous_map_id=match["previous_map_id"],
            previous_map_md5=match["previous_map_md5"],
            slots=slot_models,
            channel_name=match["channel_name"],
            seed=match["seed"],
        )

        self.redis_connection.set(
            f"bancho:matches:{match_id}",
            json.dumps(match_model),
        )

        return match

    def fetch_all(self) -> list[Match]:
        matches: list[Match] = []

        match_key: bytes
        for match_key in self.redis_connection.scan_iter("bancho:matches:*"):
            # match_id = int(match_key.decode().split(":")[-1])

            raw_match = self.redis_connection.get(match_key)
            if raw_match is None:
                continue

            match: MatchModel = json.loads(raw_match)

            slots = [
                Slot(
                    user_id=slot["user_id"],
                    mods=Mods(slot["mods"]),
                    status=SlotStatus(slot["status"]),
                    team=Team(slot["team"]),
                )
                for slot in match["slots"]
            ]

            matches.append(
                Match(
                    match_id=match["match_id"],
                    host_id=match["host_id"],
                    password=match["password"],
                    in_progress=match["in_progress"],
                    free_mod=match["free_mod"],
                    game_mode=GameMode(match["game_mode"]),
                    mods=Mods(match["mods"]),
                    match_name=match["match_name"],
                    win_condition=WinConditions(match["win_condition"]),
                    team_type=TeamTypes(match["team_type"]),
                    current_map_name=match["current_map_name"],
                    current_map_id=match["current_map_id"],
                    current_map_md5=match["current_map_md5"],
                    previous_map_name=match["previous_map_name"],
                    previous_map_id=match["previous_map_id"],
                    previous_map_md5=match["previous_map_md5"],
                    slots=slots,
                    channel_name=match["channel_name"],
                    seed=match["seed"],
                )
            )

        return matches
