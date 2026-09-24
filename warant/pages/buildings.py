"""Buildings page state & view (Colony Buildings + Defense Facilities)."""

from __future__ import annotations

import reflex as rx
from sqlmodel import select

from .. import engine
from .. import gamedata as g
from ..components.layout import (
    C_BLUE,
    C_DIM,
    C_GREEN,
    C_TEXT,
    game_shell,
    page_title,
    panel,
    pixel_img,
    progress_bar,
)
from ..db import game_session
from ..game_state import GameState
from ..models import BroodJob, ConstructionJob, Player


def _defense_row(
    key: str,
    nest,
    brood_lvl: int,
    research: dict[str, int],
    army: dict[str, int],
    count_input: str = "1",
) -> list:
    u = g.UNITS[key]
    locked = ""
    if u.req_research and research.get(u.req_research, 0) < u.req_research_level:
        locked = f"{g.RESEARCH[u.req_research].name} {u.req_research_level}단계 필요"
    t = g.unit_build_time(key, brood_lvl, research.get("metabolism", 0))
    stat_line = f"공 {u.attack} · 방 {u.defense} · 체 {u.hull}"
    stationed = army.get(key, 0)
    return [
        key,
        f"/img/u_{key}.svg",
        u.name,
        u.desc,
        stat_line,
        f"{int(u.food):,}",
        f"{int(u.water):,}",
        g.fmt_duration(t),
        locked,
        count_input,
        stationed,
    ]


class BuildingsState(GameState):
    tab: str = "buildings"  # "buildings" | "defense"
    rows: list[list] = []
    # [key, icon, name, desc, level, effect_now, effect_next,
    #  cost_f, cost_w, time_str, afford, queued, maxed]
    defense_rows: list[list] = []
    # [key, icon, name, desc, stat_line, cost_f, cost_w, time_str, locked, count, stationed]
    defense_jobs: list[list] = []
    # [icon, name, remaining, pct]

    def _sync_page_data(self, s, pid: int, nest):
        levels = engine.building_levels(s, nest.id)
        research = engine.research_levels(s, pid)
        brood_lvl = levels.get("brood_chamber", 1)
        army = engine.army_at(s, nest.id)

        # 1. Building upgrades
        cjob = s.exec(
            select(ConstructionJob).where(ConstructionJob.nest_id == nest.id)
        ).first()
        queued_key = cjob.key if cjob else ""
        rows = []
        for key in g.BUILDING_ORDER:
            lvl = levels.get(key, 0)
            b = g.BUILDINGS[key]
            cf, cw = g.building_cost(key, lvl + 1)
            t = g.building_time(key, lvl + 1)
            maxed = lvl >= b.max_level
            eff_next = "" if maxed else _effect_text(key, lvl + 1)
            afford = bool(nest.res_food >= cf and nest.res_water >= cw) and not maxed
            rows.append(
                [
                    key,
                    f"/img/b_{key}.svg",
                    b.name,
                    b.desc,
                    lvl,
                    _effect_text(key, lvl),
                    eff_next,
                    int(cf),
                    int(cw),
                    g.fmt_duration(t),
                    afford,
                    (queued_key == key) and not maxed,
                    maxed,
                ]
            )
        self.rows = rows

        # 2. Defense rows (preserve user input count)
        cur_counts = {row[0]: row[9] for row in self.defense_rows if len(row) >= 10}
        self.defense_rows = [
            _defense_row(
                key, nest, brood_lvl, research, army, count_input=cur_counts.get(key, "1")
            )
            for key in g.DEFENSE_ORDER
        ]

        # 3. Defense jobs
        d_jobs = []
        for j in s.exec(
            select(BroodJob).where(BroodJob.nest_id == nest.id)
        ).all():
            if j.unit_key in g.DEFENSE_ORDER:
                unit_sec = max(j.unit_seconds, 0.001)
                elapsed = max(0.0, (g.utc_now() - j.started_at).total_seconds())
                cur_progress = elapsed % unit_sec
                pct = int(min(100, max(0, cur_progress / unit_sec * 100)))
                d_jobs.append(
                    [
                        j.id,
                        f"/img/u_{j.unit_key}.svg",
                        g.UNITS[j.unit_key].name,
                        j.count,
                        pct,
                    ]
                )
        self.defense_jobs = d_jobs

    @rx.event
    def set_tab(self, tab: str | list[str]):
        if isinstance(tab, list):
            self.tab = tab[0] if tab else "buildings"
        else:
            self.tab = str(tab)

    @rx.event(background=True)
    async def load(self):
        async with self:
            if self._require_login():
                return
            self._sync_game()

    @rx.event(background=True)
    async def cancel_construction(self):
        async with self:
            if self._require_login():
                return
            with game_session() as s:
                nest = self._nest(s)
                if nest is None:
                    return
                ok, b_name, rf, rw = engine.cancel_construction(s, nest.id)
                if ok:
                    s.commit()
                    self.toast = f"{b_name} 공사가 취소되었습니다. (자원 50% 반환: 먹이 +{int(rf):,}, 물 +{int(rw):,})"
                else:
                    self.toast = "건설 작업을 취소할 수 없습니다."
        yield BuildingsState.load

    @rx.event(background=True)
    async def cancel_defense_job(self, job_id: int):
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
                    self.toast = f"{u_name} ×{cnt}개 제작이 취소되었습니다. (자원 50% 반환: 먹이 +{int(rf):,}, 물 +{int(rw):,})"
                else:
                    self.toast = "제작 작업을 취소할 수 없습니다."
        yield BuildingsState.load

    @rx.event(background=True)
    async def upgrade(self, key: str):
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
                busy = s.exec(
                    select(ConstructionJob).where(ConstructionJob.nest_id == nest.id)
                ).first()
                if busy:
                    msg = "이미 건설 중인 건물이 있습니다."
                else:
                    lvl = engine.get_building_level(s, nest.id, key)
                    b = g.BUILDINGS[key]
                    if lvl + 1 > b.max_level:
                        msg = "최대 단계입니다."
                    else:
                        cf, cw = g.building_cost(key, lvl + 1)
                        if nest.res_food < cf or nest.res_water < cw:
                            msg = "자원이 부족합니다."
                        elif not engine.consume_energy(
                            session=s, player=player,
                            amount=g.COST_BUILD_UPGRADE,
                        ):
                            msg = f"행동 에너지가 부족합니다 ({int(g.COST_BUILD_UPGRADE)} 필요)."
                        else:
                            t = g.building_time(key, lvl + 1)
                            s.add(
                                ConstructionJob(
                                    nest_id=nest.id,
                                    key=key,
                                    target_level=lvl + 1,
                                    started_at=g.utc_now(),
                                    completes_at=g.utc_now()
                                    + __import__("datetime").timedelta(seconds=t),
                                )
                            )
                            msg = (
                                f"{b.name} {lvl + 1}단계 공사 시작! "
                                f"(에너지 -{int(g.COST_BUILD_UPGRADE)})"
                            )
                s.commit()
            self.toast = msg
        yield BuildingsState.load

    @rx.event(background=True)
    async def start_defense(self, key: str):
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
                else:
                    cnt = 1
                    for row in self.defense_rows:
                        if row[0] == key:
                            try:
                                cnt = max(1, min(9999, int(row[9])))
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
                        msg = f"{u.name} ×{cnt} 만들기 시작! (에너지 -{int(g.COST_BROOD_BATCH)})"
                s.commit()
            self.toast = msg
        yield BuildingsState.load

    @rx.event
    def set_defense_count(self, key: str, value: str):
        self.defense_rows = [
            (
                row[:9] + [value] + row[10:]
                if row[0] == key
                else row
            )
            for row in self.defense_rows
        ]


EFFECT_FMT = {
    "fungus_farm": lambda lvl: f"먹이 +{g.building_prod('fungus_farm', lvl)[0]:,.0f}/h",
    "dew_collector": lambda lvl: f"물 +{g.building_prod('dew_collector', lvl)[1]:,.0f}/h",
    "sun_chamber": lambda lvl: f"에너지 회복 +{int(g.SUN_CHAMBER_REGEN_BONUS * lvl * 100)}%",
    "granary": lambda lvl: f"저장고 {g.fmt_num(g.storage_capacity(lvl))}",
    "living_quarters": lambda lvl: f"개미 수용 한도 {g.ant_population_cap(lvl):,}마리",
    "tunnel_network": lambda lvl: f"숨긴 자원 {g.fmt_num(g.hidden_resources(lvl))}",
}


def _effect_text(key: str, lvl: int) -> str:
    if key in EFFECT_FMT:
        return EFFECT_FMT[key](lvl)
    if key == "brood_chamber":
        return f"생산 시간 -{int(min(70, 7 * max(0, lvl - 1)))}%"
    if key == "research_chamber":
        return f"연구 시간 -{int(min(70, 6 * max(0, lvl - 1)))}% / 연구 상한 {g.max_research_level(lvl)}단계"
    if key == "thorn_gate":
        return f"수비력 +{int(8 * lvl)}%"
    if key == "watch_post":
        return f"정찰 저항 +{25 * lvl}"
    return ""


def _building_card(row) -> rx.Component:
    key, icon, name, desc, lvl, eff_now, eff_next, cf, cw, t_str, afford, queued, maxed = (
        row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8],
        row[9], row[10], row[11], row[12],
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
                    rx.text(name, weight="bold", size="3", color=C_TEXT),
                    rx.badge(lvl.to(str), "단계", color_scheme="amber",
                             variant="surface"),
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
            res_mini("/img/res_food.svg", cf.to(str), C_GREEN),
            res_mini("/img/res_water.svg", cw.to(str), C_BLUE),
            rx.text("⏱ ", t_str, size="1", color=C_DIM),
            rx.spacer(),
            rx.badge("⚡ 8", variant="surface"),
            spacing="2",
            align="center",
            width="100%",
        ),
        rx.cond(
            maxed,
            rx.text(eff_now, size="1", color=C_GREEN),
            rx.hstack(
                rx.text(eff_now, size="1", color=C_DIM),
                rx.text("→", size="1", color=C_DIM),
                rx.text(eff_next, size="1", color=C_GREEN),
                spacing="2",
            ),
        ),
        rx.cond(
            maxed,
            rx.button("최대 단계", disabled=True, width="100%", size="2"),
            rx.cond(
                queued,
                rx.hstack(
                    rx.button("건설 중...", disabled=True, flex="1", size="2",
                              color_scheme="amber"),
                    rx.button(
                        "취소",
                        size="2",
                        variant="surface",
                        color_scheme="red",
                        on_click=BuildingsState.cancel_construction,
                    ),
                    spacing="2",
                    width="100%",
                ),
                rx.button(
                    "업그레이드",
                    width="100%",
                    size="2",
                    color_scheme="grass",
                    disabled=~afford,
                    on_click=lambda: BuildingsState.upgrade(key),
                ),
            ),
        ),
        spacing="2",
    )


def _defense_job_row(j) -> rx.Component:
    job_id = j[0]
    return rx.vstack(
        rx.hstack(
            pixel_img(j[1], 20),
            rx.text(j[2], size="2", weight="bold"),
            rx.spacer(),
            rx.text(j[3].to(str), "개 남음", size="1", color=C_DIM),
            rx.button(
                "취소",
                size="1",
                variant="surface",
                color_scheme="red",
                on_click=lambda: BuildingsState.cancel_defense_job(job_id),
            ),
            spacing="2",
            align="center",
            width="100%",
        ),
        progress_bar(j[4], C_GREEN),
        spacing="1",
        width="100%",
    )


def _defense_card(row) -> rx.Component:
    key, icon, name, desc, stat_line, cf, cw, t_str, locked, count, stationed = (
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
                    rx.badge(rx.text("보유 ", stationed.to(str), "개"), color_scheme="blue", variant="surface"),
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
            res_mini("/img/res_food.svg", cf, C_GREEN),
            res_mini("/img/res_water.svg", cw, C_BLUE),
            rx.text("⏱ ", t_str, "/개", size="1", color=C_DIM),
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
                    on_change=lambda v: BuildingsState.set_defense_count(key, v),
                ),
                rx.button(
                    "만들기",
                    flex="1",
                    size="2",
                    color_scheme="grass",
                    on_click=lambda: BuildingsState.start_defense(key),
                ),
                spacing="2",
                width="100%",
            ),
        ),
        spacing="2",
    )


def res_mini(icon: str, text: str, color: str) -> rx.Component:
    return rx.hstack(
        pixel_img(icon, 14),
        rx.text(text, size="1", color=color),
        spacing="1",
        align="center",
    )


def buildings_page() -> rx.Component:
    return game_shell(
        "/buildings",
        page_title("건설", "/img/icon_hammer.svg"),
        rx.segmented_control.root(
            rx.segmented_control.item("건물", value="buildings"),
            rx.segmented_control.item("방어 시설", value="defense"),
            value=BuildingsState.tab,
            on_change=BuildingsState.set_tab,
            width="100%",
            size="2",
        ),
        rx.cond(
            BuildingsState.tab == "buildings",
            rx.vstack(
                rx.cond(
                    GameState.has_construction,
                    panel(
                        rx.hstack(
                            pixel_img("/img/icon_hammer.svg", 20),
                            rx.text(GameState.construction_label, size="2", weight="bold"),
                            rx.spacer(),
                            rx.text(GameState.construction_eta, size="1", color=C_DIM),
                            rx.button(
                                "취소",
                                size="1",
                                variant="surface",
                                color_scheme="red",
                                on_click=BuildingsState.cancel_construction,
                            ),
                            spacing="2",
                            align="center",
                            width="100%",
                        ),
                        progress_bar(GameState.construction_done_pct),
                        spacing="2",
                    ),
                ),
                rx.foreach(BuildingsState.rows, _building_card),
                spacing="3",
                width="100%",
            ),
            rx.vstack(
                rx.cond(
                    BuildingsState.defense_jobs.length() > 0,
                    panel(
                        rx.heading("제작 중", size="4"),
                        rx.vstack(
                            rx.foreach(BuildingsState.defense_jobs, _defense_job_row),
                            spacing="3",
                            width="100%",
                        ),
                        spacing="3",
                    ),
                ),
                rx.foreach(BuildingsState.defense_rows, _defense_card),
                spacing="3",
                width="100%",
            ),
        ),
        on_load=[BuildingsState.load],
    )
