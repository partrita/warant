"""Authentication state: register, login, logout with signed cookie tokens."""

from __future__ import annotations

import hashlib
import hmac
import os

import reflex as rx
import sqlmodel
from bcrypt import checkpw, gensalt, hashpw

from . import engine
from .db import game_session
from .models import Army, BuildingLevel, Nest, Player, Report

_SECRET = os.environ.get("WARANT_SECRET", "warant-dev-secret-change-me")


def hash_password(password: str) -> str:
    return hashpw(password.encode(), gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def make_token(player_id: int) -> str:
    sig = hmac.new(_SECRET.encode(), str(player_id).encode(), hashlib.sha256)
    return f"{player_id}.{sig.hexdigest()[:32]}"


def parse_token(token: str | None) -> int | None:
    if not token or "." not in token:
        return None
    pid_s, sig = token.split(".", 1)
    expected = make_token(int(pid_s)).split(".", 1)[1]
    if not hmac.compare_digest(expected, sig):
        return None
    return int(pid_s)


class AuthState(rx.State):
    """Session handling shared by every game page via substates."""

    token: str = rx.Cookie(name="warant_session", max_age=60 * 60 * 24 * 30)
    auth_error: str = ""
    auth_busy: bool = False
    username: str = ""

    def _player_id(self) -> int | None:
        return parse_token(self.token)

    @rx.event
    def register(self, form: dict) -> rx.event.EventSpec | list[rx.event.EventSpec]:
        username = (form.get("username") or "").strip()
        password = form.get("password") or ""
        if not (2 <= len(username) <= 20):
            self.auth_error = "이름은 2~20자로 입력하세요."
            return
        if len(password) < 4:
            self.auth_error = "비밀번호는 4자 이상 입력하세요."
            return
        with game_session() as s:
            exists = s.exec(
                sqlmodel.select(Player).where(Player.username == username)
            ).first()
            if exists:
                self.auth_error = "이미 존재하는 여왕 이름입니다."
                return
            player = Player(username=username, password_hash=hash_password(password))
            s.add(player)
            s.flush()

            import secrets as _secrets

            x, y = engine.find_free_coord(s, _secrets.SystemRandom())
            nest = Nest(
                player_id=player.id,
                name=f"{username}의 둥지",
                x=x,
                y=y,
                is_main=True,
            )
            s.add(nest)
            s.flush()
            for key in (
                "fungus_farm",
                "dew_collector",
                "sun_chamber",
                "granary",
                "brood_chamber",
            ):
                s.add(BuildingLevel(nest_id=nest.id, key=key, level=1))
            s.add(Army(nest_id=nest.id, unit_key="worker", count=8))

            welcome = Report(
                player_id=player.id,
                kind="system",
                title=f"왕국 건립을 축하합니다, 여왕 {username}님!",
            )
            welcome.set_body(
                {
                    "text": (
                        "첫 콜로니가 세워졌습니다. 버섯 농장과 이슬 수집기로 자원을 모으고, "
                        "육아방에서 개미를 부화시켜 세력을 넓히세요. 지도에서 사냥터를 찾아 "
                        "사냥대를 보내면 큰 수확을 얻을 수 있습니다."
                    ),
                    "coord": f"{x}:{y}",
                }
            )
            s.add(welcome)
            s.commit()
            pid = player.id
        self.auth_error = ""
        self.token = make_token(pid)
        self.username = username
        return rx.redirect("/colony")

    @rx.event
    def login(self, form: dict) -> rx.event.EventSpec | list[rx.event.EventSpec]:
        username = (form.get("username") or "").strip()
        password = form.get("password") or ""
        with game_session() as s:
            player = s.exec(
                sqlmodel.select(Player).where(Player.username == username)
            ).first()
            if not player or not verify_password(password, player.password_hash):
                self.auth_error = "이름 또는 비밀번호가 올바르지 않습니다."
                return
            pid = player.id
            uname = player.username
        self.auth_error = ""
        self.token = make_token(pid)
        self.username = uname
        return rx.redirect("/colony")

    @rx.event
    def logout(self) -> rx.event.EventSpec | list[rx.event.EventSpec]:
        self.token = ""
        self.reset()
        return rx.redirect("/")
