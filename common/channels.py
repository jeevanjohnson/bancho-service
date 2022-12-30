from enums.privileges import ServerPrivileges
from objects.channels import Channel
from objects.collections import Channels

# fmt: off
_channels: Channels = Channels.from_channels([
    Channel(
        name="#osu",
        description="main osu! channel",
        auto_join=True,
        privileges=ServerPrivileges.Normal,
    ),
    Channel(
        name="#lobby",
        description="main osu! lobby channel",
        auto_join=False,
        privileges=ServerPrivileges.Normal,
    ),
])
# fmt: on
