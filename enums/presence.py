import enum


@enum.unique
class PresenceFilter(enum.IntEnum):
    """osu! client side filter for which users the player can see."""

    Nil = 0
    All = 1
    Friends = 2
