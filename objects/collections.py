from typing import Any, Callable, Optional, Sequence

import packets
from objects.channels import Channel
from objects.osu_session import OsuSession


class Channels(list[Channel]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_from_name(self, name: str) -> Optional[Channel]:
        for channel in self:
            if channel.name == name:
                return channel

    @classmethod
    def from_channels(cls, channel_list: list[Channel]) -> "Channels":
        channels = cls()
        channels.extend(channel_list)
        return channels


class OsuSessions(list[OsuSession]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_from_key_value(self, key: str, value: Any) -> Optional[list[OsuSession]]:
        if isinstance(value, Sequence):
            session = [sess for sess in self if sess[key] in value]
        else:
            session = [sess for sess in self if sess[key] == value]

        if not session:
            return None
        else:
            return session

    def get_from_token(self, token: str) -> Optional[OsuSession]:
        value = self.get_from_key_value(
            key="cho_token",
            value=token,
        )

        if value is None:
            return None
        else:
            return value[0]

    def get_from_user_id(self, user_id: int) -> Optional[OsuSession]:
        value = self.get_from_key_value(
            key="user_id",
            value=user_id,
        )

        if value is None:
            return None
        else:
            return value[0]

    def get_from_user_ids(self, user_ids: list[int]) -> Optional[list[OsuSession]]:
        value = self.get_from_key_value(
            key="user_id",
            value=user_ids,
        )

        if value is None:
            return None
        else:
            return value

    def send_to_all(self, data: bytes) -> None:
        for session in self:
            if session.is_bot:
                continue
            
            session.packet_queue += data

    def send_to_all_but(
        self,
        excluded: list[OsuSession],
        data: bytes,
    ) -> None:
        for session in self:
            if session.is_bot:
                continue
            
            if session in excluded:
                continue
                
            session.packet_queue += data

    def send_to_all_if(
        self,
        condition: Callable[[OsuSession], bool],
        data: bytes,
    ) -> None:
        ...

    def collect_all_sessions_for(self, osu_session: OsuSession) -> bytes:
        data = bytearray()

        user_id = osu_session.user_id

        for session in self:
            if session.is_bot:
                continue
            
            if session.user_id == user_id:
                continue
            
            data += packets.pack_osu_session(session)

        return bytes(data)

    def collect_all_data(self) -> bytes:
        ...
