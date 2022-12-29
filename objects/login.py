from dataclasses import dataclass


@dataclass
class ClientDetails:
    osu_version: float
    osu_path_md5: str
    adapters_md5: str
    uninstall_md5: str
    disk_signature_md5: str
    adapters: list[str]

    @classmethod
    def from_osu_client_login(
        cls,
        osu_version: str,
        client_hashes: list[str],
    ) -> "ClientDetails":
        (
            osu_path_md5,
            adapters,
            adapters_md5,
            uninstall_md5,
            disk_signature_md5,
        ) = client_hashes
        return cls(
            osu_version=float(
                osu_version.removeprefix("b"),
            ),
            osu_path_md5=osu_path_md5,
            adapters_md5=adapters_md5,
            uninstall_md5=uninstall_md5,
            disk_signature_md5=disk_signature_md5,
            adapters=adapters.split("."),
        )


@dataclass
class LoginData:
    user_name: str
    pass_md5: str
    utc_offset: int
    display_city: bool
    pm_private: bool
    client_details: ClientDetails

    @classmethod
    def from_osu_client_login(
        cls,
        user_name: str,
        pass_md5: str,
        osu_version: str,
        utc_offset: str,
        display_city: str,
        client_hashes: str,
        pm_private: str,
    ) -> "LoginData":
        client_details = ClientDetails.from_osu_client_login(
            osu_version=osu_version,
            client_hashes=[item for item in client_hashes.split(":") if item],
        )

        return cls(
            user_name,
            pass_md5,
            int(utc_offset),
            False if display_city == "0" else True,
            False if pm_private == "0" else True,
            client_details,
        )
