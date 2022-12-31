from typing import TypedDict
import json
from fakeredis._server import FakeStrictRedis
from typing import Optional
from repositories.accounts import Account
from repositories.channels import ChannelModel
from database.models import AcountModelAsDict
from enums.actions import ActionType
from enums.mods import Mods
from enums.game_mode import GameMode

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

    def update(
        self,
        token: str,
        new_session: Session,
    ) -> Session:
        account = AcountModelAsDict(
            id=new_session["account"]["id"],
            user_name=new_session["account"]["user_name"],
            email_address=new_session["account"]["email_address"],
            password_argon2=new_session["account"]["password_argon2"],
            friends=json.dumps(new_session["account"]["friends"]),
            country_code=new_session["account"]["country_code"],
            privileges=new_session["account"]["privileges"],
        )
        session_model = SessionModel(
            account=account,
            utc_offset=new_session["utc_offset"],
            last_pinged=new_session["last_pinged"],
            match=new_session["match"],
            channels_in=json.dumps(new_session["channels_in"]),
            status=new_session["status"],
            status_text=new_session["status_text"],
            current_map_md5=new_session["current_map_md5"],
            current_mods=new_session["current_mods"],
            current_game_mode=new_session["current_game_mode"],
            current_map_id=new_session["current_map_id"],
            packet_queue=json.dumps(list(new_session["packet_queue"])),
        )

        self.redis_connection.set(
            f"bancho:sessions:{token}",
            json.dumps(session_model),
        )

        return new_session

    def fetch_all(self) -> list[Session]:
        session_models = self.redis_connection.hgetall("bancho:sessions")

        token: str
        session: SessionModel

        sessions = []

        for token, session in session_models.items():
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
    ) -> Optional[Session]:
        if token is None:
            return None  # TODO: for now

        raw_session = self.redis_connection.get(f"bancho:sessions:{token}")
        if raw_session is None:
            return None

        session: SessionModel = json.loads(raw_session)

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
