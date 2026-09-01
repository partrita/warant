"""Ranking page: players & alliances."""

from __future__ import annotations

import reflex as rx
from sqlmodel import select

from .. import engine
from ..components.layout import (
    C_AMBER,
    C_DIM,
    C_GREEN,
    C_TEXT,
    game_shell,
    page_title,
    panel,
)
from ..db import game_session
from ..game_state import GameState
from ..models import Alliance, Player


class RankingState(GameState):
    players: list[list] = []  # [rank, name, points, alliance_tag]
    alliances: list[list] = []  # [rank, tag, name, total_points, member_count]

    @rx.event(background=True)
    async def load(self):
        async with self:
            if self._require_login():
                return
            self._sync_game()
            with game_session() as s:

                players = s.exec(select(Player)).all()
                scored = sorted(
                    ((p, engine.player_points(s, p.id)) for p in players),
                    key=lambda t: -t[1],
                )
                tags = {
                    a.id: a.tag for a in s.exec(select(Alliance)).all()
                }
                self.players = [
                    [
                        i + 1,
                        p.username,
                        round(pts, 1),
                        tags.get(p.alliance_id, "") if p.alliance_id else "",
                    ]
                    for i, (p, pts) in enumerate(scored[:50])
                ]
                alliances = s.exec(select(Alliance)).all()
                a_scored = []
                for a in alliances:
                    mems = s.exec(
                        select(Player).where(Player.alliance_id == a.id)
                    ).all()
                    total = sum(engine.player_points(s, m.id) for m in mems)
                    a_scored.append((a, total, len(mems)))
                a_scored.sort(key=lambda t: -t[1])
                self.alliances = [
                    [i + 1, a.tag, a.name, round(tot, 1), cnt]
                    for i, (a, tot, cnt) in enumerate(a_scored)
                ]
                s.commit()


def _medal(rank) -> rx.Component:
    return rx.cond(
        rank == 1,
        rx.text("🥇", size="2", weight="bold", width="36px", color=C_AMBER),
        rx.cond(
            rank == 2,
            rx.text("🥈", size="2", weight="bold", width="36px", color=C_AMBER),
            rx.cond(
                rank == 3,
                rx.text("🥉", size="2", weight="bold", width="36px", color=C_AMBER),
                rx.text(rank.to(str), size="2", weight="bold", width="36px",
                        color=C_AMBER),
            ),
        ),
    )


def _player_row(r) -> rx.Component:
    return rx.hstack(
        _medal(r[0]),
        rx.text(r[1], size="2", weight="bold", color=C_TEXT),
        rx.cond(
            r[3] != "",
            rx.badge(r[3], variant="surface"),
            rx.fragment(),
        ),
        rx.spacer(),
        rx.text(r[2].to(str), "점", size="1", color=C_GREEN),
        spacing="2",
        align="center",
        width="100%",
        padding_y="6px",
        border_bottom="1px solid #33291f",
    )


def _alliance_row(a) -> rx.Component:
    return rx.hstack(
        _medal(a[0]),
        rx.badge(a[1], variant="surface"),
        rx.text(a[2], size="2", weight="bold"),
        rx.spacer(),
        rx.text(a[4].to(str), "명 · ", a[3].to(str), "점", size="1", color=C_DIM),
        spacing="2",
        align="center",
        width="100%",
        padding_y="6px",
        border_bottom="1px solid #33291f",
    )


def ranking_page() -> rx.Component:
    return game_shell(
        "/more/ranking",
        page_title("랭킹", "/img/icon_trophy.svg"),
        panel(
            rx.heading("여왕 랭킹", size="4"),
            rx.vstack(
                rx.foreach(RankingState.players, _player_row),
                spacing="0",
                width="100%",
            ),
            spacing="2",
        ),
        panel(
            rx.heading("동맹 랭킹", size="4"),
            rx.cond(
                RankingState.alliances.length() > 0,
                rx.vstack(
                    rx.foreach(RankingState.alliances, _alliance_row),
                    spacing="0",
                    width="100%",
                ),
                rx.text("아직 동맹이 없습니다.", size="2", color=C_DIM),
            ),
            spacing="2",
        ),
        on_load=[RankingState.load],
    )
