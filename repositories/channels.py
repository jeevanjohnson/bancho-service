import json
from typing import Optional, TypedDict

from fakeredis._server import FakeStrictRedis

from enums.privileges import ServerPrivileges

SERVER_PRIVILEGES = int
JSON = str
TOKEN = str


class Channel(TypedDict):
    # "x" is what the function returns
    name: str
    description: str
    auto_join: bool
    sessions_in: list[TOKEN]
    privileges: ServerPrivileges


class ChannelModel(TypedDict):
    # "xModel" is what goes into the database
    name: str
    description: str
    auto_join: bool
    sessions_in: JSON
    privileges: SERVER_PRIVILEGES


class ChannelRepo:
    # fetch_one
    # fetch_many
    # fetch_all
    # delete
    # update
    # create
    # commit
    def __init__(self, redis_connection: FakeStrictRedis) -> None:
        self.redis_connection = redis_connection

    def update(self, name: str, updated_channel: Channel) -> Channel:
        channel_model = ChannelModel(
            name=updated_channel["name"],
            description=updated_channel["description"],
            auto_join=updated_channel["auto_join"],
            sessions_in=json.dumps(updated_channel["sessions_in"]),
            privileges=int(updated_channel["privileges"]),
        )

        self.redis_connection.set(
            f"bancho:channels:{name}",
            json.dumps(channel_model),
        )

        return updated_channel

    def fetch_many(
        self,
        names: Optional[list[str]] = None,
    ) -> list[Channel]:
        channels = []

        key: bytes
        for key in self.redis_connection.scan_iter("bancho:channels:*"):
            channel_name = key.decode().split(":")[-1]

            if names and channel_name not in names:
                continue

            raw_channel = self.redis_connection.get(key)
            if raw_channel is None:
                continue

            channel: ChannelModel = json.loads(raw_channel)

            channels.append(
                Channel(
                    name=channel["name"],
                    description=channel["description"],
                    auto_join=channel["auto_join"],
                    sessions_in=json.loads(channel["sessions_in"]),
                    privileges=ServerPrivileges(channel["privileges"]),
                )
            )

        return channels

    def fetch_one(
        self,
        name: Optional[str] = None,
    ) -> Optional[Channel]:
        if name is None:
            return None  # TODO: for now

        raw_channel = self.redis_connection.get(f"bancho:channels:{name}")
        if raw_channel is None:
            return None

        channel: ChannelModel = json.loads(raw_channel)

        return Channel(
            name=channel["name"],
            description=channel["description"],
            auto_join=channel["auto_join"],
            sessions_in=json.loads(channel["sessions_in"]),
            privileges=ServerPrivileges(channel["privileges"]),
        )

    def create(
        self,
        name: str,
        description: str,
        auto_join: bool,
        privileges: ServerPrivileges,
    ) -> Channel:

        channel = Channel(
            name=name,
            description=description,
            auto_join=auto_join,
            privileges=privileges,
            sessions_in=[],
        )

        channel_model = ChannelModel(
            name=channel["name"],
            description=channel["description"],
            auto_join=channel["auto_join"],
            privileges=int(channel["privileges"]),
            sessions_in=json.dumps(channel["sessions_in"]),
        )

        self.redis_connection.set(
            f"bancho:channels:{name}",
            json.dumps(channel_model),
        )

        return channel
