import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

import constants
import packets
from enums.actions import ActionType
from enums.game_mode import GameMode
from enums.mods import Mods
from enums.multiplayer import SlotStatus, Team, TeamTypes
from enums.presence import PresenceFilter
from enums.privileges import ClientPrivileges, ServerPrivileges
from objects.command import Command, Context
from objects.login import ClientDetails

if TYPE_CHECKING:
    from objects.channels import Channel
    from objects.matches import Match

from utils import error

# import common

USER_ID = int


@dataclass
class Status:
    action: ActionType
    info_text: str
    map_id: int
    map_md5: str
    mode: GameMode
    mods: Mods


DEFAULT_STATUS = Status(
    action=ActionType.Idle,
    info_text="",
    map_id=0,
    map_md5="",
    mode=GameMode.vn_std,
    mods=Mods.NOMOD,
)


@dataclass
class Account:
    user_id: int
    user_name: str
    friends: list[USER_ID]
    country_code: str


class OsuClient:
    def __init__(
        self,
        details: ClientDetails,
        status: Status = DEFAULT_STATUS,
        presence_filter: PresenceFilter = PresenceFilter.All,
        pending_packets: bytearray = bytearray(),
    ) -> None:
        self.details: ClientDetails = details
        self.status: Status = status
        self.presence_filter: PresenceFilter = presence_filter
        self.pending_packets: bytearray = pending_packets

    def notify(self, message: str) -> None:
        self.pending_packets += packets.notification(message)
        return None

    def join_match(self, match: "Match") -> None:
        self.pending_packets += packets.match_join_sucess(
            match=match, send_pass_word=True
        )
        return None

    def joining_match_failed(self) -> None:
        self.pending_packets += packets.match_join_fail()
        return None

    def see_match(self, match: "Match") -> None:
        breakpoint()

    def join_channel(self, channel: "Channel") -> None:
        channel_bytes = packets.channel_info(
            channel_name=channel.name,
            channel_description=channel.description,
            channel_player_count=channel.player_count,
        )
        channel_bytes += packets.channel_info_end()
        channel_bytes += packets.channel_join(channel.name)

        self.pending_packets += channel_bytes

        return None

    def leave_channel(self, channel: "Channel") -> None:
        self.pending_packets += packets.channel_kick(
            channel_name=channel.name,
        )

        return None

    def server_to_client_privileges(
        self, server_privileges: ServerPrivileges
    ) -> ClientPrivileges:
        client_privs = ClientPrivileges.Player

        if server_privileges & ServerPrivileges.Normal:
            client_privs |= ClientPrivileges.Supporter

        if server_privileges & (ServerPrivileges.Admin | ServerPrivileges.Mod):
            client_privs |= ClientPrivileges.Moderator

        if server_privileges & ServerPrivileges.EventManager:
            client_privs |= ClientPrivileges.Tournament

        if server_privileges & ServerPrivileges.Developer:
            client_privs |= ClientPrivileges.Developer

        if server_privileges & ServerPrivileges.Owner:
            client_privs |= ClientPrivileges.Owner

        return client_privs

    def clear_pending_packets(self) -> bytearray:
        _queue = self.pending_packets.copy()
        self.pending_packets.clear()
        return _queue

    def country_code_to_client_code(self, country_code: str) -> int:
        return constants.time.country_codes_to_osu_code[country_code]


@dataclass
class Session:
    account: Account
    osu_client: OsuClient

    cho_token: str
    utc_offset: int
    privileges: ServerPrivileges
    last_pinged: float
    channels_in: list["Channel"] = field(default_factory=list)

    def join_match(
        self,
        match: "Match",
        match_pass_word: Optional[str] = None,
    ) -> None:
        # TODO: more checks?
        if match.pass_word is not None:
            if match.pass_word != match_pass_word:
                self.osu_client.joining_match_failed()
                return None

        avaliable_slots = [slot for slot in match.slots if slot.user_id is None]

        if not avaliable_slots:
            self.osu_client.joining_match_failed()
            self.osu_client.notify("match is full")
            return None

        slot = avaliable_slots[0]

        slot.user_id = self.account.user_id
        slot.status = SlotStatus.NOT_READY

        if match.team_type in (TeamTypes.TEAM_VS, TeamTypes.TAG_TEAM_VS):
            slot.team = Team.RED

        self.channels_in.append(match.channel)

        self.osu_client.join_match(match)

    def join_channel(self, channel: "Channel") -> None:
        if self in channel:
            return None

        channel.add_session(self)

        self.channels_in.append(channel)

        self.osu_client.join_channel(channel)  # TODO: move this to the top?

    def leave_channel(self, channel: "Channel") -> None:
        # ensure the client is has left the channel
        self.osu_client.leave_channel(channel)

        if self not in channel:
            return None  # error("user is already not in channel")

        channel.remove_session(self)

        self.channels_in.remove(channel)

    @property
    def is_bot(self) -> bool:
        return self.account.user_id == 3
