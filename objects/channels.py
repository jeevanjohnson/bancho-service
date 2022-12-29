from enums.privileges import ServerPrivileges
from objects.osu_session import OsuSession


class Channel:
    def __init__(
        self,
        name: str,
        description: str,
        privs: ServerPrivileges,
    ) -> None:
        self.name = name
        self.description = description
        self.privs = privs

        self.osu_sessions: list[OsuSession] = []

    @property
    def player_count(self):
        return len(self.osu_sessions)

    def add_session(self, session: OsuSession) -> None:
        self.osu_sessions.append(session)

    def remove_player(self, session: OsuSession) -> None:
        self.osu_sessions.remove(session)
