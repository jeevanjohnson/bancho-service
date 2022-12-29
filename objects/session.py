import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import constants
import packets
from enums.actions import ActionType
from enums.game_mode import GameMode
from enums.mods import Mods
from enums.presence import PresenceFilter
from enums.privileges import ClientPrivileges, ServerPrivileges
from objects.command import Command, Context
from objects.login import ClientDetails

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from objects.channels import Channel
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
        packet_queue: bytearray = bytearray(),
    ) -> None:
        self.details: ClientDetails = details
        self.status: Status = status
        self.presence_filter: PresenceFilter = presence_filter
        self.packet_queue: bytearray = packet_queue

    def join_channel(self, channel: "Channel") -> None:
        channel_bytes = packets.channel_info(
            channel_name=channel.name,
            channel_description=channel.description,
            channel_player_count=channel.player_count,
        )
        channel_bytes += packets.channel_info_end()
        channel_bytes += packets.channel_join(channel.name)

        self.packet_queue += channel_bytes

        return None

    def leave_channel(self, channel: "Channel") -> None:
        self.packet_queue += packets.channel_kick(
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

    def clear_packet_queue(self) -> bytearray:
        _queue = self.packet_queue.copy()
        self.packet_queue.clear()
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

    def join_channel(self, channel: "Channel") -> None:
        if self in channel:
            return None

        channel.add_session(self)

        self.channels_in.append(channel)

        self.osu_client.join_channel(channel)

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


# class Bot(Session):
#    def __init__(self):
#        client_details = ClientDetails(
#            osu_version=0.0,
#            osu_path_md5="",
#            adapters_md5="",
#            uninstall_md5="",
#            disk_signature_md5="",
#            adapters=[""],
#        )
#        super().__init__(
#            cho_token=str(uuid.uuid1()),
#            user_id=3,
#            user_name="coveri",
#            friends=[],
#            utc_offset=-8,
#            country_code="us",
#            client_details=client_details,
#            privs=ServerPrivileges.Owner,
#            last_pinged=0.0,
#        )
#
#        self.commands: list[Command] = []
#
#    async def process_command(
#        self, command: str, osu_session: OsuSession
#    ) -> Optional[str]:
#        if command.startswith("!"):
#            command = command.removeprefix("!")
#
#        cmd_name, *args = command.split(" ", maxsplit=1)
#
#        context = Context(
#            osu_session=osu_session,
#            args=args,
#        )
#
#        for cmd in self.commands:
#            if cmd_name in cmd.alias or cmd_name == cmd.name:
#                # TODO: parse args, fix this type
#                message = await cmd.command_function(context)  # type: ignore
#                return message
#
