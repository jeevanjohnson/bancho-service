import enum


@enum.unique
class TeamTypes(enum.IntEnum):
    HEAD_TO_HEAD = 0
    TAG_COOP = 1
    TEAM_VS = 2
    TAG_TEAM_VS = 3


@enum.unique
class WinConditions(enum.IntEnum):
    SCORE = 0
    ACCURACY = 1
    COMBO = 2
    SCORE_V2 = 3


@enum.unique
class Team(enum.IntEnum):
    NEUTRAL = 0
    BLUE = 1
    RED = 2


@enum.unique
class SlotStatus(enum.IntEnum):
    OPEN = 1
    LOCKED = 2
    NOT_READY = 4
    READY = 8
    NO_MAP = 16
    PLAYING = 32
    COMPLETE = 64
    QUIT = 128

    HAS_PLAYER = NOT_READY | READY | NO_MAP | PLAYING | COMPLETE
