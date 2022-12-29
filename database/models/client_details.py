from typing import Optional

from sqlmodel import Field, SQLModel

from database.types import JSON


class ClientDetail(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int
    osu_version: float
    osu_path_md5: str
    adapters_md5: str
    uninstall_md5: str
    disk_signature_md5: str
    adapters: JSON
    country_code: str
    login_date: float
