import enum


@enum.unique
class GameMode(enum.IntEnum):
    vn_std = 0
    vn_taiko = 1
    vn_catch = 2
    vn_mania = 3

    rx_std = 4
    rx_taiko = 5
    rx_catch = 6

    ap_std = 7

    @property
    def as_osu_client(self) -> "GameMode":
        if self in (self.rx_std, self.rx_taiko, self.rx_catch):
            self -= 4
        elif self == self.ap_std:
            self -= 8

        return GameMode(self)
