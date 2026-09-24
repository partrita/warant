"""Brood (unit production) page state & view."""

from __future__ import annotations

import reflex as rx
from sqlmodel import select

from .. import engine
from .. import gamedata as g
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


def queued_mobile_ants(session, nest_id: int) -> int:
    """Count mobile ants already committed to brood queues."""
    return sum(
        j.count
        for j in session.exec(select(BroodJob).where(BroodJob.nest_id == nest_id)).all()
        if j.unit_key in g.UNIT_ORDER
    )


def _unit_row(
    key: str,
    nest: Nest,
    brood_lvl: int,
    research: dict[str, int],
    available_pop: int,
    count_input: int = 1,
) -> list:
    u = g.UNITS[key]
    locked = ""
    if u.req_research and research.get(u.req_research, 0) < u.req_research_level:
        locked = f"{g.RESEARCH[u.req_research].name} {u.req_research_level}단계 필요"
    t = g.unit_build_time(key, brood_lvl, research.get("metabolism", 0))
    stat_line = (
        f"공 {u.attack} · 방 {u.defense} · 체 {u.hull}"
        + f" · 속도 {u.speed}"
        + (f" · 운반 {u.cargo}" if u.cargo else "")
    )

    if locked:
        max_hatchable = 0
    else:
        max_f = int(nest.res_food // u.food) if u.food > 0 else 9999
        max_w = int(nest.res_water // u.water) if u.water > 0 else 9999
        max_hatchable = max(0, min(max_f, max_w, available_pop))

    if max_hatchable > 0:
        c = max(1, min(count_input, max_hatchable))
    else:
        c = 0

    return [
        key,
        f"/img/u_{key}.svg",
        u.name,
        u.desc,
        "이동 부대",
        stat_line,
        f"{int(u.food):,}",
        f"{int(u.water):,}",
        g.fmt_duration(t),
        locked,
        c,              # row[10]: count
        max_hatchable,  # row[11]: max_hatchable
    ]


class BroodState(GameState):
    unit_rows: list[list] = []
    # [key, icon, name, desc, badge, stat_line, cost_f, cost_w, time_str, locked, count, max_hatchable]
    jobs: list[list] = []  # [id, icon, name, remaining, pct, unit_key]
    army_chips: list[list] = []  # [icon, name, count]
    brood_level: int = 0
    ant_population: int = 0
    ant_population_cap: int = g.BASE_ANT_CAP

    def _sync_page_data(self, s, pid: int, nest):
        research = engine.research_levels(s, pid)
        brood_lvl = engine.get_building_level(s, nest.id, "brood_chamber")
        housing_lvl = engine.get_building_level(s, nest.id, "living_quarters")
        self.brood_level = brood_lvl
        self.ant_population_cap = g.ant_population_cap(housing_lvl)
        army = engine.army_at(s, nest.id)
        current = sum(army.get(key, 0) for key in g.UNIT_ORDER)
        queued = queued_mobile_ants(s, nest.id)
        self.ant_population = current
        available_pop = max(0, self.ant_population_cap - current - queued)

        cur_counts = {}
        for row in self.unit_rows:
            if len(row) >= 11:
                try:
                    cur_counts[row[0]] = int(row[10])
                except (ValueError, TypeError):
                    cur_counts[row[0]] = 1

        self.unit_rows = [
            _unit_row(
                key,
                nest,
                brood_lvl,
                research,
                available_pop,
                count_input=cur_counts.get(key, 1),
            )
            for key in g.UNIT_ORDER
        ]

        jobs_out = []
        for j in s.exec(
            select(BroodJob).where(BroodJob.nest_id == nest.id)
        ).all():
            if j.unit_key not in g.UNIT_ORDER:
                continue
            unit_sec = max(j.unit_seconds, 0.001)
            elapsed = max(0.0, (g.utc_now() - j.started_at).total_seconds())
            cur_progress = elapsed % unit_sec
            pct = int(min(100, max(0, cur_progress / unit_sec * 100)))
            jobs_out.append(
                [
                    j.id,
                    f"/img/u_{j.unit_key}.svg",
                    g.UNITS[j.unit_key].name,
                    j.count,
                    pct,
                    j.unit_key,
                ]
            )
        self.jobs = jobs_out

        self.army_chips = [
            [f"/img/u_{k}.svg", g.UNITS[k].name, v]
            for k, v in sorted(army.items())
            if v > 0 and k in g.UNIT_ORDER
        ]

    @rx.event(background=True)
    async def load(self):
        async with self:
            if self._require_login():
                return
            self._sync_game()

    @rx.event
    def set_slider_count(self, key: str, val: list[int] | int):
        c = val[0] if isinstance(val, list) else int(val)
        self.unit_rows = [
            (
                row[:10] + [c] + row[11:]
                if row[0] == key
                else row
            )
            for row in self.unit_rows
        ]

    @rx.event
    def set_max_count(self, key: str):
        self.unit_rows = [
            (
                row[:10] + [row[11]] + row[11:]
                if row[0] == key
                else row
            )
            for row in self.unit_rows
        ]

    @rx.event(background=True)
    async def cancel_brood_job(self, job_id: int):
        async with self:
            if self._require_login():
                return
            with game_session() as s:
                nest = self._nest(s)
                if nest is None:
                    return
                ok, u_name, cnt, rf, rw = engine.cancel_brood_job(s, job_id, nest.id)
                if ok:
                    s.commit()
                    self.toast = f"{u_name} ×{cnt}마리 부화가 취소되었습니다. (자원 50% 반환: 먹이 +{int(rf):,}, 물 +{int(rw):,})"
                else:
                    self.toast = "부화 작업을 취소할 수 없습니다."
        yield BroodState.load

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
                            except (ValueError, TypeError):
                                cnt = 1
                            break

                    if key in g.UNIT_ORDER:
                        army = engine.army_at(s, nest.id)
                        current = sum(army.get(unit_key, 0) for unit_key in g.UNIT_ORDER)
                        queued = queued_mobile_ants(s, nest.id)
                        housing_lvl = engine.get_building_level(s, nest.id, "living_quarters")
                        cap = g.ant_population_cap(housing_lvl)
                        available = max(0, cap - current - queued)
                        if cnt > available:
                            msg = (
                                f"둥지 개미 수 한도 초과입니다. "
                                f"현재 {current + queued:,}/{cap:,}마리, "
                                f"최대 {available:,}마리까지 부화할 수 있습니다. "
                                f"(건설 > 개미 숙소를 확장하세요)"
                            )
                            s.commit()
                            self.toast = msg
                            return

                    cost_f = u.food * cnt
                    cost_w = u.water * cnt
                    if nest.res_food < cost_f or nest.res_water < cost_w:
                        msg = f"자원이 부족합니다 ({u.name} ×{cnt})."
                    elif not engine.consume_energy(
                        session=s, player=player, amount=g.COST_BROOD_BATCH
                    ):
                        msg = f"행동 에너지가 부족합니다 ({int(g.COST_BROOD_BATCH)} 필요)."
                    else:
                        nest.res_food -= cost_f
                        nest.res_water -= cost_w
                        s.add(nest)
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
                    s.commit()
            self.toast = msg
        yield BroodState.load


def _job_row(j) -> rx.Component:
    job_id = j[0]
    return rx.vstack(
        rx.hstack(
            pixel_img(j[1], 20),
            rx.text(j[2], size="2", weight="bold"),
            rx.spacer(),
            rx.text(j[3].to(str), "마리 남음", size="1", color=C_DIM),
            rx.button(
                "취소",
                size="1",
                variant="surface",
                color_scheme="red",
                on_click=lambda: BroodState.cancel_brood_job(job_id),
            ),
            spacing="2",
            align="center",
            width="100%",
        ),
        progress_bar(j[4], C_GREEN),
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
    key, icon, name, desc, badge, stat_line, cf, cw, t_str, locked = (
        row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8],
        row[9],
    )
    count = row[10].to(int)
    max_hatchable = row[11].to(int)
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
            rx.vstack(
                rx.hstack(
                    rx.text("부화 수량:", size="2", color=C_DIM),
                    rx.badge(count.to(str), "마리", color_scheme="amber", size="2"),
                    rx.spacer(),
                    rx.text("최대 가능: ", max_hatchable.to(str), "마리", size="1", color=C_DIM),
                    rx.button(
                        "최대",
                        size="1",
                        variant="surface",
                        color_scheme="gray",
                        disabled=max_hatchable <= 0,
                        on_click=lambda: BroodState.set_max_count(key),
                    ),
                    spacing="2",
                    align="center",
                    width="100%",
                ),
                rx.slider(
                    value=[count],
                    min=rx.cond(max_hatchable > 0, 1, 0),
                    max=rx.cond(max_hatchable > 0, max_hatchable, 1),
                    step=1,
                    disabled=max_hatchable <= 0,
                    on_change=lambda v: BroodState.set_slider_count(key, v),
                    width="100%",
                ),
                rx.button(
                    rx.cond(
                        max_hatchable > 0,
                        "부화 시작 (" + count.to(str) + "마리)",
                        "자원 / 주거지 부족",
                    ),
                    disabled=max_hatchable <= 0,
                    width="100%",
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
        panel(
            rx.hstack(
                pixel_img("/img/u_worker.svg", 22),
                rx.text("둥지 개미", size="2", weight="bold"),
                rx.spacer(),
                rx.text(
                    BroodState.ant_population.to(str),
                    " / ",
                    BroodState.ant_population_cap.to(str),
                    "마리",
                    size="2",
                    weight="bold",
                    color=C_GREEN,
                ),
                spacing="2",
                width="100%",
            ),
            rx.text(
                "기본 한도 50마리 · 개미 숙소 건설로 주거 한도를 확장할 수 있습니다.",
                size="1",
                color=C_DIM,
            ),
            spacing="2",
        ),
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

