from typing import Optional

from enums.privileges import ServerPrivileges
from objects.session import Session


class Channel:
    def __init__(
        self,
        name: str,
        description: str,
        auto_join: bool,
        privileges: ServerPrivileges = ServerPrivileges.Normal,
    ) -> None:
        self.name = name
        self.description = description
        self.auto_join = auto_join
        self.privileges = privileges

        self.sessions: list[Session] = []

    @property
    def player_count(self):
        return len(self.sessions)

    def add_session(self, session: Session) -> None:
        self.sessions.append(session)

    def remove_session(self, session: Session) -> None:
        self.sessions.remove(session)

    def __contains__(self, session: Session) -> bool:
        return session in self.sessions
