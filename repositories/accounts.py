import json
from typing import Optional, TypedDict

from sqlmodel import Session as DatabaseSession
from sqlmodel import select

from database.models import AccountModel
from enums.privileges import ServerPrivileges


class Account(TypedDict):
    # "x" is what the function returns
    id: int
    user_name: str
    email_address: str
    password_argon2: str
    friends: list[int]
    country_code: str
    privileges: int


class AccountRepo:
    # fetch_one
    # fetch_many
    # fetch_all
    # delete
    # update
    # create
    # commit
    def __init__(self, database_session: DatabaseSession) -> None:
        self.database_session = database_session

    def fetch_all(self) -> list[Account]:
        query = select(AccountModel)
        accounts_from_database = self.database_session.exec(query).all()

        accounts = []

        for account in accounts_from_database:
            accounts.append(
                Account(
                    id=account.id,
                    user_name=account.user_name,
                    email_address=account.email_address,
                    password_argon2=account.password_argon2,
                    friends=json.loads(account.friends),
                    country_code=account.country_code,
                    privileges=account.privileges,
                )
            )

        return accounts

    def create(
        self,
        user_id: int,
        user_name: str,
        email_address: str,
        password_argon2: str,
        friends: list[int],
        country_code: str,
        privileges: ServerPrivileges,
    ) -> Account:
        model = AccountModel(
            id=user_id,
            user_name=user_name,
            email_address=email_address,
            password_argon2=password_argon2,
            friends=json.dumps(friends),
            country_code=country_code,
            privileges=privileges,
        )

        self.database_session.add(model)

        return Account(
            id=user_id,
            user_name=user_name,
            email_address=email_address,
            password_argon2=password_argon2,
            friends=friends,
            country_code=country_code,
            privileges=privileges,
        )

    def fetch_one(
        self,
        user_id: Optional[int] = None,
        user_name: Optional[str] = None,
        country_code: Optional[str] = None,
        email_address: Optional[str] = None,
    ) -> Optional[Account]:

        filter_parms = {}

        if user_id is not None:
            filter_parms["id"] = user_id

        if user_name is not None:
            filter_parms["user_name"] = user_name

        if country_code is not None:
            filter_parms["country_code"] = country_code

        if email_address is not None:
            filter_parms["email_address"] = email_address

        # fmt: off
        # TODO: figure out why this doesn't work
        # query = select(Account).where((
        #     Account.id == sqlalchemy.func.coalesce(user_id, Account.id) and 
        #     Account.user_name == sqlalchemy.func.coalesce(user_name, Account.user_name) and
        #     Account.country_code == sqlalchemy.func.coalesce(country_code, Account.country_code) and
        #     Account.email_address == sqlalchemy.func.coalesce(email_address, Account.email_address)
        # ))
        # # fmt: on
        # print(query)

        query = select(AccountModel).filter_by(**filter_parms)
        account = self.database_session.exec(query).first()

        if account is None:
            return None
        else:
            return Account(
                id=account.id,
                user_name=account.user_name,
                email_address=account.email_address,
                password_argon2=account.password_argon2,
                friends=json.loads(account.friends),
                country_code=account.country_code,
                privileges=account.privileges,
            )

    def commit(self) -> None:
        self.database_session.commit()

        return None
