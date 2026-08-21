"""More menu: research, reports, alliance, ranking, settings."""

from __future__ import annotations

import reflex as rx

from ..auth_state import AuthState
from ..components.layout import (
    C_DIM,
    C_TEXT,
    game_shell,
    page_title,
    panel,
    pixel_img,
)
from ..game_state import GameState


def _menu_row(icon: str, label: str, sub: str, href: str) -> rx.Component:
    return rx.link(
        rx.hstack(
            pixel_img(icon, 30),
            rx.vstack(
                rx.text(label, size="3", weight="bold", color=C_TEXT),
                rx.text(sub, size="1", color=C_DIM),
                spacing="0",
                align="start",
            ),
            rx.spacer(),
            rx.text("›", size="4", color=C_DIM),
            spacing="3",
            align="center",
            width="100%",
        ),
        href=href,
        text_decoration="none",
        width="100%",
    )


def more_page() -> rx.Component:
    return game_shell(
        "/more",
        page_title("더보기"),
        panel(
            _menu_row("/img/b_research_chamber.svg", "연구",
                      "기술을 연구해 왕국을 강화하세요", "/more/research"),
            _menu_row("/img/icon_report.svg", "보고서",
                      "전투·정찰·사냥 결과를 확인하세요", "/more/reports"),
            _menu_row("/img/icon_flag.svg", "동맹",
                      "함께 싸울 동료를 찾으세요", "/more/alliance"),
            _menu_row("/img/icon_trophy.svg", "랭킹",
                      "세계 정복의 순위를 확인하세요", "/more/ranking"),
            spacing="2",
        ),
        panel(
            rx.heading("설정", size="4"),
            rx.hstack(
                rx.text("여왕: ", size="2", color=C_DIM),
                rx.badge(AuthState.username, variant="surface"),
                rx.spacer(),
                rx.badge("⚡ ", GameState.energy_disp,
                         variant="surface"),
                spacing="2",
                width="100%",
            ),
            rx.button(
                "로그아웃",
                variant="surface",
                color_scheme="red",
                width="100%",
                size="2",
                on_click=AuthState.logout,
            ),
            spacing="3",
        ),
        panel(
            rx.text("WarAnt v0.1 — 여왕개미 콜로니 전략 게임", size="1", color=C_DIM),
            rx.text("먹이 · 물 · 행동 에너지로 세계를 정복하세요.", size="1", color=C_DIM),
            spacing="1",
        ),
        on_load=[GameState.refresh_game],
    )
