from typing import Optional

from sqlmodel import Field, SQLModel

from database.types import JSON, PRIVILEGES


class Account(SQLModel, table=True):
    id: int = Field(default=3, primary_key=True)
    user_name: str
    pass_argon2: str
    friends: JSON
    country_code: str
    privileges: PRIVILEGES
