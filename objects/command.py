from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Optional, Sequence

from enums.privileges import ServerPrivileges

if TYPE_CHECKING:
    from objects.session import Session


@dataclass
class Context:
    osu_session: "Session"
    args: Sequence[str]


@dataclass
class Command:
    name: str
    description: str
    command_function: Callable[[Context], Optional[str]]  # [Context], Optional[str]]
    privileges: ServerPrivileges
    alias: list[str] = field(default_factory=list)
