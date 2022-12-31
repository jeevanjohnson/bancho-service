import json
from typing import Optional, TypedDict

from fakeredis._server import FakeStrictRedis

from database.models import AcountModelAsDict
from enums.actions import ActionType
from enums.game_mode import GameMode
from enums.mods import Mods
from repositories.accounts import Account
from repositories.channels import ChannelModel

CHANNEL_NAME = str
MATCH_ID = int
JSON = str
TOKEN = str


class Session(TypedDict):
    # "x" is what the function returns
    token: str

    account: Account

    utc_offset: int
    last_pinged: float

    match: Optional[MATCH_ID]

    channels_in: list[CHANNEL_NAME]

    status: ActionType
    status_text: str
    current_map_md5: str
    current_mods: Mods
    current_game_mode: GameMode
    current_map_id: int

    packet_queue: bytearray


class SessionModel(TypedDict):
    # "xModel" is what goes into the database
    account: AcountModelAsDict

    utc_offset: int
    last_pinged: float

    match: Optional[MATCH_ID]

    channels_in: JSON

    status: int
    status_text: str
    current_map_md5: str
    current_mods: int
    current_game_mode: int
    current_map_id: int

    packet_queue: JSON


class SessionRepo:
    # fetch_one
    # fetch_many
    # fetch_all
    # delete
    # update
    # create
    # commit
    def __init__(self, redis_connection: FakeStrictRedis) -> None:
        self.redis_connection = redis_connection

    def fetch_many(
        self,
        user_ids: Optional[list[int]] = None,  # TODO: more parameters
    ) -> list[Session]:
        token_keys: list[bytes] = self.redis_connection.keys("bancho:sessions:*")
        tokens = [key.decode().split(":")[-1] for key in token_keys]

        valid_tokens: list[str] = []
        valid_session_models: list[SessionModel] = []

        for token, raw_session in zip(
            tokens,
            self.redis_connection.mget(token_keys),
        ):
            if raw_session is None:
                continue

            session: SessionModel = json.loads(raw_session)

            if user_ids:
                if session["account"]["id"] not in user_ids:
                    continue

            valid_tokens.append(token)
            valid_session_models.append(session)

        token: str
        session: SessionModel

        sessions = []

        for token, session in zip(valid_tokens, valid_session_models):
            account = Account(
                id=session["account"]["id"],
                user_name=session["account"]["user_name"],
                email_address=session["account"]["email_address"],
                password_argon2=session["account"]["password_argon2"],
                friends=json.loads(session["account"]["friends"]),
                country_code=session["account"]["country_code"],
                privileges=session["account"]["privileges"],
            )
            sessions.append(
                Session(
                    token=token,
                    account=account,
                    utc_offset=session["utc_offset"],
                    last_pinged=session["last_pinged"],
                    match=session["match"],
                    channels_in=json.loads(session["channels_in"]),
                    status=ActionType(session["status"]),
                    status_text=session["status_text"],
                    current_map_md5=session["current_map_md5"],
                    current_mods=Mods(session["current_mods"]),
                    current_game_mode=GameMode(session["current_game_mode"]),
                    current_map_id=session["current_map_id"],
                    packet_queue=bytearray(json.loads(session["packet_queue"])),
                )
            )

        return sessions

    def update(
        self,
        token: str,
        updated_session: Session,
    ) -> Session:
        account = AcountModelAsDict(
            id=updated_session["account"]["id"],
            user_name=updated_session["account"]["user_name"],
            email_address=updated_session["account"]["email_address"],
            password_argon2=updated_session["account"]["password_argon2"],
            friends=json.dumps(updated_session["account"]["friends"]),
            country_code=updated_session["account"]["country_code"],
            privileges=updated_session["account"]["privileges"],
        )
        session_model = SessionModel(
            account=account,
            utc_offset=updated_session["utc_offset"],
            last_pinged=updated_session["last_pinged"],
            match=updated_session["match"],
            channels_in=json.dumps(updated_session["channels_in"]),
            status=updated_session["status"],
            status_text=updated_session["status_text"],
            current_map_md5=updated_session["current_map_md5"],
            current_mods=updated_session["current_mods"],
            current_game_mode=updated_session["current_game_mode"],
            current_map_id=updated_session["current_map_id"],
            packet_queue=json.dumps(list(updated_session["packet_queue"])),
        )

        self.redis_connection.set(
            f"bancho:sessions:{token}",
            json.dumps(session_model),
        )

        return updated_session

    def fetch_all(self) -> list[Session]:
        tokens_key: list[bytes] = self.redis_connection.keys("bancho:sessions:*")
        tokens: list[str] = [key.decode().split(":")[-1] for key in tokens_key]

        session_models: list[SessionModel] = []

        for raw_session in self.redis_connection.mget(tokens_key):
            if raw_session is None:
                continue

            session_models.append(json.loads(raw_session))

        token: str
        session: SessionModel

        sessions = []

        for token, session in zip(tokens, session_models):
            account = Account(
                id=session["account"]["id"],
                user_name=session["account"]["user_name"],
                email_address=session["account"]["email_address"],
                password_argon2=session["account"]["password_argon2"],
                friends=json.loads(session["account"]["friends"]),
                country_code=session["account"]["country_code"],
                privileges=session["account"]["privileges"],
            )
            sessions.append(
                Session(
                    token=token,
                    account=account,
                    utc_offset=session["utc_offset"],
                    last_pinged=session["last_pinged"],
                    match=session["match"],
                    channels_in=json.loads(session["channels_in"]),
                    status=ActionType(session["status"]),
                    status_text=session["status_text"],
                    current_map_md5=session["current_map_md5"],
                    current_mods=Mods(session["current_mods"]),
                    current_game_mode=GameMode(session["current_game_mode"]),
                    current_map_id=session["current_map_id"],
                    packet_queue=bytearray(json.loads(session["packet_queue"])),
                )
            )

        return sessions

    def fetch_one(
        self,
        token: Optional[str] = None,  # TODO: support other fetch methods
        user_name: Optional[str] = None,
    ) -> Optional[Session]:
        # TODO: make this cleaner
        if token:
            raw_session = self.redis_connection.get(f"bancho:sessions:{token}")
            if raw_session is None:
                return None

            session: SessionModel = json.loads(raw_session)
        else:
            # TODO: find a better way because scaling from here is not that fun
            tokens = self.redis_connection.keys("bancho:sessions:*")

            if not tokens:
                return None

            session_models: list[SessionModel] = []

            for raw_session in self.redis_connection.mget(tokens):
                if raw_session is None:
                    continue

                session_models.append(json.loads(raw_session))

            if not session_models:
                return None

            session_token: str
            session: SessionModel

            for session_token, session in zip(tokens, session_models):
                if session["account"]["user_name"] == user_name:
                    token = session_token
                    break
            else:
                return None

        account = Account(
            id=session["account"]["id"],
            user_name=session["account"]["user_name"],
            email_address=session["account"]["email_address"],
            password_argon2=session["account"]["password_argon2"],
            friends=json.loads(session["account"]["friends"]),
            country_code=session["account"]["country_code"],
            privileges=session["account"]["privileges"],
        )

        return Session(
            token=token,
            account=account,
            utc_offset=session["utc_offset"],
            last_pinged=session["last_pinged"],
            match=session["match"],
            channels_in=json.loads(session["channels_in"]),
            status=ActionType(session["status"]),
            status_text=session["status_text"],
            current_map_md5=session["current_map_md5"],
            current_mods=Mods(session["current_mods"]),
            current_game_mode=GameMode(session["current_game_mode"]),
            current_map_id=session["current_map_id"],
            packet_queue=bytearray(json.loads(session["packet_queue"])),
        )

    def create(
        self,
        token: str,
        account: Account,
        last_pinged: float,
        utc_offset: int,
        channels_in: list[CHANNEL_NAME],
        match: Optional[int] = None,
        packet_queue: bytearray = bytearray(),
    ) -> Session:
        session_key = f"bancho:sessions:{token}"
        session = Session(
            token=token,
            account=account,
            last_pinged=last_pinged,
            channels_in=channels_in,
            match=match,
            packet_queue=packet_queue,
            status=ActionType.Idle,
            status_text="",
            current_map_md5="",
            current_mods=Mods.NOMOD,
            current_game_mode=GameMode.vn_std,
            current_map_id=0,
            utc_offset=utc_offset,
        )

        account_model_as_dict = AcountModelAsDict(
            id=account["id"],
            user_name=account["user_name"],
            email_address=account["email_address"],
            password_argon2=account["password_argon2"],
            friends=json.dumps(account["friends"]),
            country_code=account["country_code"],
            privileges=account["privileges"],
        )

        session_model = SessionModel(
            last_pinged=session["last_pinged"],
            channels_in=json.dumps(session["channels_in"]),
            match=session["match"],
            packet_queue=json.dumps(list(session["packet_queue"])),
            account=account_model_as_dict,
            status=int(session["status"]),
            status_text=session["status_text"],
            current_map_md5=session["current_map_md5"],
            current_mods=int(session["current_mods"]),
            current_game_mode=int(session["current_game_mode"]),
            current_map_id=session["current_map_id"],
            utc_offset=session["utc_offset"],
        )
        self.redis_connection.set(
            session_key,
            json.dumps(session_model),
        )

        channel_key_fmt = "bancho:channels:{}"
        for channel_name in session["channels_in"]:
            channel_key = channel_key_fmt.format(channel_name)
            raw_channel = self.redis_connection.get(channel_key)

            assert raw_channel, "this should not happen"

            channel: ChannelModel = json.loads(raw_channel)

            sessions_in: list[TOKEN] = json.loads(channel["sessions_in"])

            sessions_in.append(session["token"])

            channel["sessions_in"] = json.dumps(sessions_in)

            self.redis_connection.set(
                channel_key,
                json.dumps(channel),
            )

        return session
