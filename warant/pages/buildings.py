"""Buildings page state & view."""

from __future__ import annotations

import reflex as rx
from sqlmodel import select

from .. import engine, gamedata as g
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
from ..models import ConstructionJob, Player


class BuildingsState(GameState):
    rows: list[list] = []
    # [key, icon, name, desc, level, effect_now, effect_next,
    #  cost_f, cost_w, time_str, afford, queued, maxed]

    @rx.event(background=True)
    async def load(self):
        await GameState.refresh_game()
        async with self:
            if self._require_login():
                return
            with game_session() as s:
                nest = self._nest(s)
                if nest is None:
                    return
                levels = engine.building_levels(s, nest.id)
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
                s.commit()

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
                # already constructing here?
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


EFFECT_FMT = {
    "fungus_farm": lambda lvl: f"먹이 +{g.building_prod('fungus_farm', lvl)[0]:,.0f}/h",
    "dew_collector": lambda lvl: f"물 +{g.building_prod('dew_collector', lvl)[1]:,.0f}/h",
    "sun_chamber": lambda lvl: f"에너지 회복 +{int(g.SUN_CHAMBER_REGEN_BONUS * lvl * 100)}%",
    "granary": lambda lvl: f"저장고 {g.fmt_num(g.storage_capacity(lvl))}",
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
                rx.button("건설 중...", disabled=True, width="100%", size="2",
                          color_scheme="amber"),
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
        rx.cond(
            GameState.has_construction,
            panel(
                rx.hstack(
                    pixel_img("/img/icon_hammer.svg", 20),
                    rx.text(GameState.construction_label, size="2", weight="bold"),
                    rx.spacer(),
                    rx.text(GameState.construction_eta, size="1", color=C_DIM),
                    spacing="2",
                    width="100%",
                ),
                progress_bar(GameState.construction_done_pct),
                spacing="2",
            ),
        ),
        rx.vstack(
            rx.foreach(BuildingsState.rows, _building_card),
            spacing="3",
            width="100%",
        ),
        on_load=[BuildingsState.load],
    )
