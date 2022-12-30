from enums.game_mode import GameMode
from enums.mods import Mods


def ensure_mods_and_gamemode(mods: int, game_mode: int) -> tuple[Mods, GameMode]:
    if mods & Mods.RELAX:
        if game_mode == GameMode.vn_mania:
            mods &= ~Mods.RELAX
        else:
            game_mode += 4
    elif mods & Mods.AUTOPILOT:
        if game_mode in (GameMode.vn_taiko, GameMode.vn_catch, GameMode.vn_mania):
            mods &= ~Mods.AUTOPILOT
        else:
            game_mode += 8

    return Mods(mods), GameMode(game_mode)
