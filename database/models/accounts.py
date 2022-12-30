import json
from typing import Optional

from sqlmodel import Field, SQLModel

from database.types import JSON, PRIVILEGES
from objects.session import Account as AccountSession


class Account(SQLModel, table=True):
    id: int = Field(default=3, primary_key=True)
    user_name: str
    pass_argon2: str
    friends: JSON
    country_code: str
    privileges: PRIVILEGES

    def as_account_session(self) -> AccountSession:
        return AccountSession(
            user_id=self.id,
            user_name=self.user_name,
            friends=json.loads(self.friends),
            country_code=self.country_code,
        )
