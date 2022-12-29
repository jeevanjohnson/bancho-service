from typing import Callable

from enums.privileges import ServerPrivileges
from objects import Command

all_commands: list[Command] = []


def command(
    name: str,
    alias: list[str] = [],
    privileges: ServerPrivileges = ServerPrivileges.Normal,
) -> Callable:
    def inner(func: Callable) -> Callable:
        alias.append(func.__name__)
        all_commands.append(
            Command(
                name=name,
                description=func.__doc__ or "No documentation for this command",
                command_function=func,
                alias=alias,
                privileges=privileges,
            )
        )
        return func

    return inner


@command(
    name="help",
)
async def help() -> str:
    return "\n".join(
        [f"!{x.name} [{' !'.join(x.alias)}] {x.description}" for x in all_commands]
    )
