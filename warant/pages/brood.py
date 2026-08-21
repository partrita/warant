"""Brood (unit production) page state & view."""

from __future__ import annotations

import reflex as rx
from sqlmodel import select

from .. import engine, gamedata as g
from ..components.layout import (
    C_BLUE,
    C_BORDER,
    C_DIM,
    C_GREEN,
    C_PANEL_2,
    C_TEXT,
    game_shell,
    page_title,
    panel,
    pixel_img,
    progress_bar,
)
from ..db import game_session
from ..game_state import GameState
from ..models import BroodJob, Nest, Player


def _unit_row(key: str, nest: Nest, brood_lvl: int, research: dict[str, int]) -> list:
    u = g.UNITS[key]
    locked = ""
    if u.req_research and research.get(u.req_research, 0) < u.req_research_level:
        locked = f"{g.RESEARCH[u.req_research].name} {u.req_research_level}단계 필요"
    t = g.unit_build_time(key, brood_lvl, research.get("metabolism", 0))
    is_def = key in g.DEFENSE_ORDER
    stat_line = (
        f"공 {u.attack} · 방 {u.defense} · 체 {u.hull}"
        + (f" · 속도 {u.speed}" if not is_def else "")
        + (f" · 운반 {u.cargo}" if u.cargo else "")
    )
    badge = "방어 시설" if is_def else "이동 부대"
    return [
        key,
        f"/img/u_{key}.svg",
        u.name,
        u.desc,
        badge,
        stat_line,
        f"{int(u.food):,}",
        f"{int(u.water):,}",
        g.fmt_duration(t),
        locked,
        "1",
    ]


class BroodState(GameState):
    unit_rows: list[list] = []
    # [key, icon, name, desc, badge, stat_line, cost_f, cost_w, time_str, locked, count_input]
    jobs: list[list] = []  # [icon, name, remaining, pct]
    army_chips: list[list] = []  # [icon, name, count]
    brood_level: int = 0

    @rx.event(background=True)
    async def load(self):
        await GameState.refresh_game()
        async with self:
            if self._require_login():
                return
            pid = self._player_id()
            with game_session() as s:
                nest = self._nest(s)
                if nest is None:
                    return
                research = engine.research_levels(s, pid)
                brood_lvl = engine.get_building_level(s, nest.id, "brood_chamber")
                self.brood_level = brood_lvl
                self.unit_rows = [
                    _unit_row(key, nest, brood_lvl, research)
                    for key in g.UNIT_ORDER + g.DEFENSE_ORDER
                ]

                jobs_out = []
                for j in s.exec(
                    select(BroodJob).where(BroodJob.nest_id == nest.id)
                ).all():
                    total = j.count * j.unit_seconds or 1
                    done = (g.utc_now() - j.started_at).total_seconds()
                    jobs_out.append(
                        [
                            f"/img/u_{j.unit_key}.svg",
                            g.UNITS[j.unit_key].name,
                            j.count,
                            int(done / total * 100),
                        ]
                    )
                self.jobs = jobs_out

                army = engine.army_at(s, nest.id)
                self.army_chips = [
                    [f"/img/u_{k}.svg", g.UNITS[k].name, v]
                    for k, v in sorted(army.items())
                    if v > 0
                ]
                s.commit()

    @rx.event(background=True)
    async def start_brood(self, key: str):
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
                research = engine.research_levels(s, pid)
                u = g.UNITS[key]
                if u.req_research and (
                    research.get(u.req_research, 0) < u.req_research_level
                ):
                    msg = "연구 조건이 부족합니다."
                    s.commit()
                else:
                    cnt = 0
                    for row in self.unit_rows:
                        if row[0] == key:
                            try:
                                cnt = max(1, min(9999, int(row[10])))
                            except ValueError:
                                cnt = 1
                            break
                    cost_f = u.food * cnt
                    cost_w = u.water * cnt
                    if nest.res_food < cost_f or nest.res_water < cost_w:
                        msg = f"자원이 부족합니다 ({u.name} ×{cnt})."
                    elif not engine.consume_energy(
                        session=s, player=player, amount=g.COST_BROOD_BATCH
                    ):
                        msg = f"행동 에너지가 부족합니다 ({int(g.COST_BROOD_BATCH)} 필요)."
                    else:
                        t = g.unit_build_time(
                            key,
                            engine.get_building_level(s, nest.id, "brood_chamber"),
                            research.get("metabolism", 0),
                        )
                        existing = s.exec(
                            select(BroodJob).where(
                                BroodJob.nest_id == nest.id, BroodJob.unit_key == key
                            )
                        ).first()
                        if existing:
                            existing.count += cnt
                            s.add(existing)
                        else:
                            s.add(
                                BroodJob(
                                    nest_id=nest.id,
                                    unit_key=key,
                                    count=cnt,
                                    unit_seconds=t,
                                    started_at=g.utc_now(),
                                )
                            )
                        msg = f"{u.name} ×{cnt} 부화 시작! (에너지 -{int(g.COST_BROOD_BATCH)})"
                    nest.res_food -= cost_f
                    nest.res_water -= cost_w
                    s.add(nest)
                    s.commit()
            self.toast = msg
        yield BroodState.load

    @rx.event
    def set_count(self, key: str, value: str):
        self.unit_rows = [
            (
                row[:10] + [value]
                if row[0] == key
                else row
            )
            for row in self.unit_rows
        ]


def _job_row(j) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            pixel_img(j[0], 20),
            rx.text(j[1], size="2", weight="bold"),
            rx.spacer(),
            rx.text(j[2].to(str), "마리 남음", size="1", color=C_DIM),
            spacing="2",
            width="100%",
        ),
        progress_bar(j[3], C_GREEN),
        spacing="1",
        width="100%",
    )


def _army_chip(a) -> rx.Component:
    return rx.hstack(
        pixel_img(a[0], 22),
        rx.text(a[1], size="1", color=C_TEXT),
        rx.text("×", a[2].to(str), size="2", weight="bold", color=C_GREEN),
        spacing="2",
        padding_x="8px",
        padding_y="4px",
        background=C_PANEL_2,
        border=f"1px solid {C_BORDER}",
        border_radius="8px",
        align="center",
    )


def _unit_card(row) -> rx.Component:
    key, icon, name, desc, badge, stat_line, cf, cw, t_str, locked, count = (
        row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8],
        row[9], row[10],
    )
    return panel(
        rx.hstack(
            rx.image(
                src=icon,
                width="44px",
                height="44px",
                style={"image_rendering": "pixelated"},
            ),
            rx.vstack(
                rx.hstack(
                    rx.text(name, weight="bold", size="3"),
                    rx.badge(badge, variant="surface"),
                    spacing="2",
                ),
                rx.text(desc, size="1", color=C_DIM),
                rx.text(stat_line, size="1", color=C_BLUE),
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
            rx.text("⏱ ", t_str, "/마리", size="1", color=C_DIM),
            rx.spacer(),
            rx.badge("⚡ 4", variant="surface"),
            spacing="2",
            align="center",
            width="100%",
        ),
        rx.cond(
            locked != "",
            rx.button(locked, disabled=True, width="100%", size="2", variant="surface"),
            rx.hstack(
                rx.input(
                    value=count,
                    width="72px",
                    type_="number",
                    min_=1,
                    on_change=lambda v: BroodState.set_count(key, v),
                ),
                rx.button(
                    "부화시키기",
                    flex="1",
                    size="2",
                    color_scheme="grass",
                    on_click=lambda: BroodState.start_brood(key),
                ),
                spacing="2",
                width="100%",
            ),
        ),
        spacing="2",
    )


def brood_page() -> rx.Component:
    return game_shell(
        "/brood",
        page_title("육아방 · 군세", "/img/icon_sword.svg"),
        rx.cond(
            BroodState.jobs.length() > 0,
            panel(
                rx.heading("부화 중", size="4"),
                rx.vstack(
                    rx.foreach(BroodState.jobs, _job_row), spacing="3", width="100%"
                ),
                spacing="3",
            ),
        ),
        panel(
            rx.heading("주둔 개미", size="4"),
            rx.cond(
                BroodState.army_chips.length() > 0,
                rx.flex(
                    rx.foreach(BroodState.army_chips, _army_chip),
                    flex_wrap="wrap",
                    gap="8px",
                ),
                rx.text("주둔 개미가 없습니다.", size="2", color=C_DIM),
            ),
            spacing="3",
        ),
        rx.vstack(
            rx.foreach(BroodState.unit_rows, _unit_card),
            spacing="3",
            width="100%",
        ),
        on_load=[BroodState.load],
    )
