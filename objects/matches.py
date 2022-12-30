from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import utils
from enums.game_mode import GameMode
from enums.mods import Mods
from enums.multiplayer import SlotStatus, Team, TeamTypes, WinConditions
from objects.channels import Channel

if TYPE_CHECKING:
    import packets
    from objects.session import Session


@dataclass
class MatchMapInfo:
    name: str  # map_
    id: int  # map_
    md5: str  # map_


class Slot:
    def __init__(
        self,
        mods: Mods = Mods.NOMOD,
        user_id: Optional[int] = None,
        status: SlotStatus = SlotStatus.OPEN,
        team: Team = Team.NEUTRAL,
    ) -> None:
        self.mods = mods
        self.status = status
        self.team = team
        self.user_id = user_id


class Match:
    def __init__(
        self,
        id: int,
        host_id: int,
        in_progress: bool,
        free_mod: bool,
        game_mode: GameMode,
        mods: Mods,
        name: str,
        current_map: MatchMapInfo,
        pass_word: Optional[str] = None,
        previous_map: Optional[MatchMapInfo] = None,
        win_condition: WinConditions = WinConditions.SCORE,
        team_type: TeamTypes = TeamTypes.HEAD_TO_HEAD,
    ) -> None:
        self.id = id
        self.host_id = host_id
        self.in_progress = in_progress
        self.free_mod = free_mod
        self.mods = mods
        self.game_mode = game_mode
        self.name = name
        self.pass_word = pass_word
        self.current_map = current_map
        self.previous_map = previous_map
        self.slots = [Slot() for _ in range(16)]
        self.win_condition = win_condition
        self.team_type = team_type
        self.seed = 0

        self.channel: Channel

    def init_channel(self) -> Channel:
        channel = Channel(
            name=f"#match_{self.id}",
            description=f"Multiplayer Match ({self.id})",
            auto_join=False,
        )

        self.channel = channel

        return channel

    def remove_session(self, session: "Session") -> None:
        for slot in self.slots:
            if slot.user_id == session.account.user_id:
                self.slots.remove(slot)

        session.leave_channel(self.channel)

        breakpoint()

    @classmethod
    def from_match_packet(
        cls, match: "packets.Match", match_id: Optional[int] = None
    ) -> "Match":
        if match_id is None:
            match_id = match.id

        mods, game_mode = utils.ensure_mods_and_gamemode(
            mods=match.mods,
            game_mode=match.game_mode,
        )

        match_map_info = MatchMapInfo(
            name=match.name,
            id=match.map_id,
            md5=match.map_md5,
        )

        if match.pass_word == "":
            pass_word = None
        else:
            pass_word = match.pass_word

        return cls(
            id=match_id,
            host_id=match.host_id,
            in_progress=match.in_progress,
            free_mod=match.freemods,
            game_mode=game_mode,
            mods=mods,
            name=match.name,
            pass_word=pass_word,
            current_map=match_map_info,
            win_condition=WinConditions(match.win_condition),
            team_type=TeamTypes(match.team_type),
        )
