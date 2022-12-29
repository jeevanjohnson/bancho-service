import uuid
from dataclasses import dataclass, field
from typing import Any

import constants
from enums.actions import ActionType
from enums.game_mode import GameMode
from enums.mods import Mods
from enums.presence import PresenceFilter
from enums.privileges import ClientPrivileges, ServerPrivileges
from objects.login import ClientDetails

USER_ID = int


@dataclass
class Status:
    action: ActionType
    info_text: str
    map_id: int
    map_md5: str
    mode: GameMode
    mods: Mods


def DEFAULT_STATUS() -> Status:
    return Status(
        action=ActionType.Idle,
        info_text="",
        map_id=0,
        map_md5="",
        mode=GameMode.vn_std,
        mods=Mods.NOMOD,
    )


def DEFAULT_PRESENCE() -> PresenceFilter:
    return PresenceFilter.All  # TODO: is this fine as a default?


@dataclass
class OsuSession:
    cho_token: str

    user_id: int
    user_name: str
    friends: list[USER_ID]

    utc_offset: int
    country_code: str
    client_details: ClientDetails

    privs: ServerPrivileges

    last_pinged: float

    presence_filter: PresenceFilter = field(default_factory=DEFAULT_PRESENCE)
    status: Status = field(default_factory=DEFAULT_STATUS)
    packet_queue: bytearray = field(default_factory=bytearray)

    @classmethod
    def create_bot(cls) -> "OsuSession":
        client_details = ClientDetails(
            osu_version=0.0,
            osu_path_md5="",
            adapters_md5="",
            uninstall_md5="",
            disk_signature_md5="",
            adapters=[""],
        )
        return cls(
            cho_token=str(uuid.uuid1()),
            user_id=3,
            user_name="coveri",
            friends=[],
            utc_offset=-8,
            country_code="us",
            client_details=client_details,
            privs=ServerPrivileges.Owner,
            last_pinged=0.0,
        )

    @property
    def is_bot(self) -> bool:
        return self.user_id == 3

    @property
    def osu_country_code(self) -> int:
        return constants.time.country_codes_to_osu_code[self.country_code]

    # @property
    # def country(self) -> str:
    #    breakpoint()

    @property
    def client_side_privileges(self) -> int:
        client_privs = ClientPrivileges.Player

        if self.privs & ServerPrivileges.Normal:
            client_privs |= ClientPrivileges.Supporter

        if self.privs & (ServerPrivileges.Admin | ServerPrivileges.Mod):
            client_privs |= ClientPrivileges.Moderator

        if self.privs & ServerPrivileges.EventManager:
            client_privs |= ClientPrivileges.Tournament

        if self.privs & ServerPrivileges.Developer:
            client_privs |= ClientPrivileges.Developer

        if self.privs & ServerPrivileges.Owner:
            client_privs |= ClientPrivileges.Owner

        return client_privs

    def __getitem__(self, key: Any) -> Any:
        return self.__dict__[key]

    def clear_packet_queue(self) -> bytearray:
        _queue = self.packet_queue.copy()
        self.packet_queue.clear()
        return _queue
