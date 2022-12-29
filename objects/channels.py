from enums.privileges import ServerPrivileges
from objects.session import Session
from typing import Optional


class Channel:
    def __init__(
        self,
        name: str,
        description: str,
        privileges: Optional[ServerPrivileges] = None,
    ) -> None:
        self.name = name
        self.description = description
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
