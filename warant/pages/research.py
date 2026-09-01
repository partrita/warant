"""Research page state & view."""

from __future__ import annotations

import datetime as dt

import reflex as rx
from sqlmodel import select

from .. import engine, gamedata as g
from ..components.layout import (
    C_BLUE,
    C_DIM,
    C_GREEN,
    game_shell,
    page_title,
    panel,
    pixel_img,
    progress_bar,
)
from ..db import game_session
from ..game_state import GameState
from ..models import Player, ResearchJob


class ResearchState(GameState):
    rows: list[list] = []
    # [key, icon, name, desc, level, cost_f, cost_w, time_str, locked_reason, maxed, busy]

    @rx.event(background=True)
    async def load(self):
        async with self:
            if self._require_login():
                return
            self._sync_game()
            pid = self._player_id()

            with game_session() as s:
                nest = self._nest(s)
                if nest is None:
                    return
                chamber = engine.get_building_level(s, nest.id, "research_chamber")
                levels = engine.research_levels(s, pid)
                rjob = s.exec(
                    select(ResearchJob).where(ResearchJob.player_id == pid)
                ).first()
                busy_key = rjob.key if rjob else ""
                rows = []
                for key in g.RESEARCH_ORDER:
                    r = g.RESEARCH[key]
                    lvl = levels.get(key, 0)
                    cf, cw = g.research_cost(key, lvl + 1)
                    t = g.research_time(key, lvl + 1, chamber)
                    maxed = lvl >= min(g.max_research_level(chamber), 20)
                    locked = ""
                    if chamber < r.req_chamber:
                        locked = f"연구방 {r.req_chamber}단계 필요"
                    elif r.req_research and (
                        levels.get(r.req_research, 0) < (r.req_research_level or 1)
                    ):
                        locked = (
                            f"{g.RESEARCH[r.req_research].name} "
                            f"{r.req_research_level or 1}단계 필요"
                        )
                    rows.append(
                        [
                            key,
                            RESEARCH_ICON[key],
                            r.name,
                            r.desc,
                            lvl,
                            f"{int(cf):,}",
                            f"{int(cw):,}",
                            g.fmt_duration(t),
                            locked,
                            maxed,
                            busy_key == key,
                        ]
                    )
                self.rows = rows
                s.commit()

    @rx.event(background=True)
    async def start(self, key: str):
        async with self:
            if self._require_login():
                return
            pid = self._player_id()
            msg = ""
            with game_session() as s:
                player = s.get(Player, pid)
                nest = self._nest(s)
                if nest is None:
                    return
                chamber = engine.get_building_level(s, nest.id, "research_chamber")
                busy = s.exec(
                    select(ResearchJob).where(ResearchJob.player_id == pid)
                ).first()
                levels = engine.research_levels(s, pid)
                r = g.RESEARCH[key]
                lvl = levels.get(key, 0)
                if busy:
                    msg = "이미 진행 중인 연구가 있습니다."
                elif chamber < r.req_chamber:
                    msg = f"연구방 {r.req_chamber}단계가 필요합니다."
                elif r.req_research and (
                    levels.get(r.req_research, 0) < (r.req_research_level or 1)
                ):
                    msg = "선행 연구가 부족합니다."
                elif lvl >= g.max_research_level(chamber):
                    msg = "연구방 단계 상한에 도달했습니다."
                else:
                    cf, cw = g.research_cost(key, lvl + 1)
                    if nest.res_food < cf or nest.res_water < cw:
                        msg = "자원이 부족합니다."
                    elif not engine.consume_energy(
                        session=s, player=player, amount=g.COST_RESEARCH_START
                    ):
                        msg = f"행동 에너지가 부족합니다 ({int(g.COST_RESEARCH_START)} 필요)."
                    else:
                        t = g.research_time(key, lvl + 1, chamber)
                        s.add(
                            ResearchJob(
                                player_id=pid,
                                nest_id=nest.id,
                                key=key,
                                target_level=lvl + 1,
                                started_at=g.utc_now(),
                                completes_at=g.utc_now() + dt.timedelta(seconds=t),
                            )
                        )
                        msg = f"{r.name} {lvl + 1}단계 연구 시작! (에너지 -{int(g.COST_RESEARCH_START)})"
                s.commit()
            self.toast = msg
        yield ResearchState.load


RESEARCH_ICON = {
    "foraging": "/img/res_food.svg",
    "hydration": "/img/res_water.svg",
    "metabolism": "/img/u_worker.svg",
    "chitin": "/img/icon_shield.svg",
    "mandibles": "/img/icon_sword.svg",
    "tunneling": "/img/b_tunnel_network.svg",
    "scent_tracking": "/img/u_scout.svg",
    "swarm_tactics": "/img/icon_flag.svg",
}


def _research_card(row) -> rx.Component:
    key, icon, name, desc, lvl, cf, cw, t_str, locked, maxed, busy = (
        row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8],
        row[9], row[10],
    )
    return panel(
        rx.hstack(
            pixel_img(icon, 40),
            rx.vstack(
                rx.hstack(
                    rx.text(name, weight="bold", size="3"),
                    rx.badge(lvl.to(str), "단계", variant="surface",
                             color_scheme="blue"),
                    spacing="2",
                ),
                rx.text(desc, size="1", color=C_DIM),
                spacing="1",
                align="start",
            ),
            spacing="3",
            align="center",
            width="100%",
        ),
        rx.hstack(
            pixel_img("/img/res_food.svg", 14),
            rx.text(cf, size="1", color=C_GREEN),
            pixel_img("/img/res_water.svg", 14),
            rx.text(cw, size="1", color=C_BLUE),
            rx.text("⏱ ", t_str, size="1", color=C_DIM),
            rx.spacer(),
            rx.badge("⚡ 12", variant="surface"),
            spacing="2",
            align="center",
            width="100%",
        ),
        rx.cond(
            maxed,
            rx.button("연구방 단계 상한 도달", disabled=True, width="100%", size="2"),
            rx.cond(
                locked != "",
                rx.button(locked, disabled=True, width="100%", size="2",
                          variant="surface"),
                rx.button(
                    "연구하기",
                    width="100%",
                    size="2",
                    color_scheme="blue",
                    disabled=busy,
                    on_click=lambda: ResearchState.start(key),
                ),
            ),
        ),
        spacing="2",
    )


def research_page() -> rx.Component:
    return game_shell(
        "/more/research",
        page_title("연구", "/img/b_research_chamber.svg"),
        rx.cond(
            GameState.has_research,
            panel(
                rx.hstack(
                    pixel_img("/img/b_research_chamber.svg", 20),
                    rx.text(GameState.research_label, size="2", weight="bold"),
                    rx.spacer(),
                    rx.text(GameState.research_eta, size="1", color=C_DIM),
                    spacing="2",
                    width="100%",
                ),
                progress_bar(GameState.research_done_pct, C_BLUE),
                spacing="2",
            ),
        ),
        rx.vstack(
            rx.foreach(ResearchState.rows, _research_card),
            spacing="3",
            width="100%",
        ),
        on_load=[ResearchState.load],
    )
