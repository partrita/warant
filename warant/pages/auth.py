"""Landing page: login & register."""

from __future__ import annotations

import reflex as rx

from ..auth_state import AuthState
from ..components.layout import (
    C_AMBER,
    C_BG,
    C_DIM,
    MAX_W,
    panel,
)


def _auth_tabs() -> rx.Component:
    return rx.tabs.root(
        rx.tabs.list(
            rx.tabs.trigger(rx.text("여왕 로그인"), value="login"),
            rx.tabs.trigger(rx.text("새 왕국 건립"), value="register"),
            width="100%",
        ),
        rx.tabs.content(
            rx.form(
                rx.vstack(
                    rx.input(
                        placeholder="여왕 이름",
                        name="username",
                        width="100%",
                        required=True,
                    ),
                    rx.input(
                        placeholder="비밀번호",
                        name="password",
                        type="password",
                        auto_complete="current-password",
                        width="100%",
                        required=True,
                    ),
                    rx.button(
                        "로그인",
                        type="submit",
                        width="100%",
                        color_scheme="amber",
                        size="3",
                    ),
                    spacing="3",
                    width="100%",
                ),
                on_submit=AuthState.login,
            ),
            value="login",
        ),
        rx.tabs.content(
            rx.form(
                rx.vstack(
                    rx.text(
                        "이름과 비밀번호만으로 새 왕국이 세워집니다.",
                        color=C_DIM, size="2",
                    ),
                    rx.input(
                        placeholder="여왕 이름 (2~20자)",
                        name="username",
                        width="100%",
                        required=True,
                    ),
                    rx.input(
                        placeholder="비밀번호 (4자 이상)",
                        name="password",
                        type="password",
                        auto_complete="new-password",
                        width="100%",
                        required=True,
                    ),
                    rx.button(
                        "왕국 건립하기",
                        type="submit",
                        width="100%",
                        color_scheme="grass",
                        size="3",
                    ),
                    spacing="3",
                    width="100%",
                ),
                on_submit=AuthState.register,
            ),
            value="register",
        ),
        default_value="login",
        width="100%",
        color_scheme="amber",
    )


def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.vstack(
                rx.image(
                    src="/img/queen.svg",
                    width="96px",
                    height="96px",
                    style={"image_rendering": "pixelated"},
                ),
                rx.heading(
                    "WarAnt",
                    size="9",
                    color=C_AMBER,
                    style={"font_family": "'Press Start 2P', monospace"},
                ),
                rx.text(
                    "여왕개미가 되어 콜로니를 키우고,\n사냥하고, 약탈하고, 동맹과 전쟁 속에서\n세계를 정복하세요.",
                    color=C_DIM,
                    size="2",
                    text_align="center",
                    line_height="1.8",
                ),
                align="center",
                spacing="3",
            ),
            panel(
                _auth_tabs(),
                rx.cond(
                    AuthState.auth_error != "",
                    rx.callout(
                        rx.text(AuthState.auth_error),
                        color_scheme="red",
                        size="1",
                        width="100%",
                    ),
                ),
            ),
            rx.text(
                "먹이 · 물 · 에너지 — 세 자원으로 왕국을 일으키세요",
                color=C_DIM, size="1",
            ),
            spacing="5",
            width="100%",
            max_width=MAX_W,
            padding="24px 16px 48px",
        ),
        height="100vh",
        background=C_BG,
    )


app_placeholder = None
