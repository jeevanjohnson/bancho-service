import enum


@enum.unique
class ServerPrivileges(enum.IntFlag):
    Normal = 1 << 0
    Whitelisted = 1 << 1
    Donor = 1 << 2
    Nominator = 1 << 3
    Mod = 1 << 4
    Admin = 1 << 5
    EventManager = 1 << 6
    Owner = 1 << 7
    Developer = 1 << 8

    Restricted = 1 << 9
    Banned = 1 << 10


@enum.unique
class ClientPrivileges(enum.IntFlag):
    Player = 1 << 0
    Moderator = 1 << 1
    Supporter = 1 << 2
    Owner = 1 << 3
    Developer = 1 << 4
    Tournament = 1 << 5
