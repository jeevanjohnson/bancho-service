from enums.privileges import ServerPrivileges
from objects.channels import Channel
from objects.collections import Channels

# fmt: off
_channels: Channels = Channels.from_channels([
    Channel("#osu", "main osu! channel", ServerPrivileges.Normal),
    Channel("#lobby", "main osu! lobby channel", privileges=None),
])
# fmt: on
