from typing import TypedDict


class ParseLoginDataResult(TypedDict):
    user_name: str
    password_md5: str
    utc_offset: int
    display_city: bool
    pm_private: bool
    osu_version: float
    osu_path_md5: str
    adapters_md5: str
    uninstall_md5: str
    disk_signature_md5: str
    adapters: list[str]


def parse_login_data(login_data: bytes) -> ParseLoginDataResult:
    user_name, password_md5, client_details = login_data.decode().splitlines()

    (
        osu_version,
        utc_offset,
        display_city,
        client_hashes,
        pm_private,
    ) = client_details.split("|")

    valid_client_hashes = [item for item in client_hashes.split(":") if item]

    (
        osu_path_md5,
        adapters,
        adapters_md5,
        uninstall_md5,
        disk_signature_md5,
    ) = valid_client_hashes

    utc_offset = int(utc_offset)

    return ParseLoginDataResult(
        user_name=user_name,
        password_md5=password_md5,
        utc_offset=utc_offset,
        display_city=False if display_city == "0" else True,
        pm_private=False if pm_private == "0" else True,
        osu_version=float(
            osu_version.removeprefix("b"),
        ),
        osu_path_md5=osu_path_md5,
        adapters_md5=adapters_md5,
        uninstall_md5=uninstall_md5,
        disk_signature_md5=disk_signature_md5,
        adapters=adapters.split("."),
    )
