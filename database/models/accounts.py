import json
from typing import Optional, TypedDict

from sqlmodel import Field, SQLModel

from database.types import JSON, PRIVILEGES


class AcountModelAsDict(TypedDict):
    id: int
    user_name: str
    email_address: str
    password_argon2: str
    friends: JSON
    country_code: str
    privileges: PRIVILEGES


class AccountModel(SQLModel, table=True):
    id: int = Field(default=3, primary_key=True)
    user_name: str
    email_address: str
    password_argon2: str
    friends: JSON
    country_code: str
    privileges: PRIVILEGES
