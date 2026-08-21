"""Colony overview: resources, queues, marches at a glance."""

from __future__ import annotations

import reflex as rx
from sqlmodel import select

from .. import engine, gamedata as g
from ..components.layout import (
    C_AMBER,
    C_BLUE,
    C_BORDER,
    C_DIM,
    C_GREEN,
    C_PANEL_2,
    C_RED,
    C_TEXT,
    game_shell,
    page_title,
    panel,
    pixel_img,
    progress_bar,
    res_chip,
)
from ..db import game_session
from ..game_state import GameState
from ..models import BroodJob, March, Nest


class ColonyState(GameState):
    brood_jobs: list[list] = []  # [icon, name, remaining, pct]
    marches_out: list[list] = []  # [label, icon, coord, eta, home]
    incoming_attacks: list[list] = []  # [attacker, coord, eta_str]
    army_summary: list[list] = []  # [icon, name, count]
    nest_name: str = ""
    nest_coord: str = ""
    granary_pct: int = 0
    hidden_res_str: str = "0"
    defense_bonus_pct: int = 0
    points_disp: str = "0"

    @rx.event(background=True)
    async def tick(self):
        await GameState.refresh_game()
        async with self:
            if self._require_login():
                return
            pid = self._player_id()
            with game_session() as s:
                player_nests = engine.nests_of(s, pid)
                nest = self._nest(s)
                if nest is None:
                    return
                self.nest_name = nest.name
                self.nest_coord = f"{nest.x}:{nest.y}"
                levels = engine.building_levels(s, nest.id)

                # brood queue for this nest
                jobs = s.exec(
                    select(BroodJob).where(BroodJob.nest_id == nest.id)
                ).all()
                out = []
                for j in jobs:
                    total = j.count * j.unit_seconds or 1
                    done = (g.utc_now() - j.started_at).total_seconds()
                    out.append(
                        [
                            f"/img/u_{j.unit_key}.svg",
                            g.UNITS[j.unit_key].name,
                            j.count,
                            int(min(100, max(0, done / total * 100))),
                        ]
                    )
                self.brood_jobs = out

                # marches of this player
                marches = s.exec(
                    select(March).where(
                        March.player_id == pid, March.status != "done"
                    )
                ).all()
                rows = []
                for m in marches:
                    home = session_home_name(s, m.from_nest_id)
                    if m.status == "outbound":
                        eta = g.fmt_duration((m.arrive_at - g.utc_now()).total_seconds())
                    elif m.return_at:
                        eta = "귀환 " + g.fmt_duration(
                            (m.return_at - g.utc_now()).total_seconds()
                        )
                    else:
                        eta = "-"
                    rows.append(
                        [
                            g.MARCH_NAMES.get(m.kind, m.kind),
                            MARCH_ICON.get(m.kind, "/img/icon_ant.svg"),
                            f"{m.tx}:{m.ty}",
                            eta,
                            home,
                        ]
                    )
                self.marches_out = rows

                # incoming hostile marches targeting my nests
                my_ids = {n.id for n in player_nests}
                inc = []
                all_m = s.exec(
                    select(March).where(March.status == "outbound")
                ).all()
                for m in all_m:
                    if (
                        m.kind == g.MARCH_ATTACK
                        and m.target_nest_id in my_ids
                        and m.player_id != pid
                    ):
                        attacker = s.get(Nest, m.from_nest_id)
                        aname = attacker.name if attacker else "?"
                        eta = g.fmt_duration(
                            (m.arrive_at - g.utc_now()).total_seconds()
                        )
                        target = s.get(Nest, m.target_nest_id)
                        inc.append([aname, f"{target.x}:{target.y}", eta])
                self.incoming_attacks = inc

                # stationed army
                army = engine.army_at(session=s, nest_id=nest.id)
                self.army_summary = [
                    [f"/img/u_{k}.svg", g.UNITS[k].name, v]
                    for k, v in sorted(army.items())
                ]

                cap = rates_cap(engine.building_levels(s, nest.id))
                self.granary_pct = int(
                    min(100, max(nest.res_food, nest.res_water) / cap * 100)
                )
                self.hidden_res_str = g.fmt_num(
                    g.hidden_resources(levels.get("tunnel_network", 0))
                )
                self.defense_bonus_pct = int(
                    100 * g.THORN_GATE_DEF_BONUS * levels.get("thorn_gate", 0)
                )
                s.commit()


def rates_cap(levels: dict[str, int]) -> float:
    return g.storage_capacity(levels.get("granary", 0))


def session_home_name(s, nest_id: int) -> str:
    n = s.get(Nest, nest_id)
    return n.name if n else "?"


MARCH_ICON = {
    "attack": "/img/icon_attack.svg",
    "scout": "/img/icon_scout.svg",
    "hunt": "/img/icon_hunt.svg",
    "transfer": "/img/icon_transfer.svg",
    "deploy": "/img/icon_transfer.svg",
}


def _march_row(row) -> rx.Component:
    label, icon, coord, eta, home = row[0], row[1], row[2], row[3], row[4]
    return rx.hstack(
        pixel_img(icon, 18),
        rx.vstack(
            rx.hstack(
                rx.text(label, " → ", coord, size="2", weight="bold"),
                rx.text(home, size="1", color=C_DIM),
                spacing="2",
            ),
            rx.text(eta, size="1", color=C_DIM),
            spacing="1",
        ),
        spacing="2",
        align="center",
        width="100%",
        padding="6px",
        border_radius="8px",
        background=C_PANEL_2,
    )


def colony_page() -> rx.Component:
    return game_shell(
        "/colony",
        # production panel
        panel(
            page_title("콜로니 현황", "/img/queen.svg"),
            rx.hstack(
                rx.text(GameState.points.to(str), color=C_AMBER, size="3", weight="bold"),
                rx.text("점수", color=C_DIM, size="1"),
                rx.spacer(),
                rx.text(GameState.nests_list.length().to(str), "개 둥지", color=C_DIM, size="2"),
                spacing="1",
                align="baseline",
            ),
            rx.divider(border_color=C_BORDER),
            _res_detail_row(
                "/img/res_food.svg", "먹이", GameState.res_food.to(str),
                GameState.prod_food.to(str), C_GREEN,
            ),
            _res_detail_row(
                "/img/res_water.svg", "물", GameState.res_water.to(str),
                GameState.prod_water.to(str), C_BLUE,
            ),
            rx.divider(border_color=C_BORDER),
            # action energy
            rx.hstack(
                pixel_img("/img/res_energy.svg", 24),
                rx.text("행동 에너지", size="2", weight="bold", width="86px"),
                rx.text(GameState.energy_disp, size="2", color=C_AMBER),
                spacing="2",
                align="center",
                width="100%",
            ),
            progress_bar(GameState.energy.to(int), C_AMBER),
            rx.text(
                "회복 속도: 12/시간 (양광실 +10%/단계) — "
                "업그레이드·연구·진군에 소모됩니다.",
                size="1", color=C_DIM,
            ),
            rx.text(
                "저장고 사용률", size="1", color=C_DIM,
            ),
            progress_bar(ColonyState.granary_pct, C_AMBER),
            spacing="3",
        ),
        # construction & research
        rx.hstack(
            rx.cond(
                GameState.has_construction,
                panel(
                    rx.hstack(pixel_img("/img/icon_hammer.svg", 20),
                              rx.text("건설 중", size="2", weight="bold"), spacing="2"),
                    rx.text(GameState.construction_label, size="2", color=C_TEXT),
                    progress_bar(GameState.construction_done_pct),
                    rx.text("남은 시간 ", GameState.construction_eta, size="1", color=C_DIM),
                    spacing="2",
                    flex="1", min_width="45%",
                ),
                panel(
                    rx.hstack(pixel_img("/img/icon_hammer.svg", 20),
                              rx.text("건설 대기 없음", size="2", weight="bold", color=C_DIM), spacing="2"),
                    rx.link("건물 올리기 →", href="/buildings", size="2", color=C_AMBER),
                    spacing="2",
                    flex="1", min_width="45%",
                ),
            ),
            rx.cond(
                GameState.has_research,
                panel(
                    rx.hstack(pixel_img("/img/b_research_chamber.svg", 20),
                              rx.text("연구 중", size="2", weight="bold"), spacing="2"),
                    rx.text(GameState.research_label, size="2"),
                    progress_bar(GameState.research_done_pct, C_BLUE),
                    rx.text("남은 시간 ", GameState.research_eta, size="1", color=C_DIM),
                    spacing="2",
                    flex="1", min_width="45%",
                ),
                panel(
                    rx.hstack(pixel_img("/img/b_research_chamber.svg", 20),
                              rx.text("연구 대기 없음", size="2", weight="bold", color=C_DIM), spacing="2"),
                    rx.link("연구 시작하기 →", href="/research", size="2", color=C_AMBER),
                    spacing="2",
                    flex="1", min_width="45%",
                ),
            ),
            width="100%",
            spacing="3",
            wrap="wrap",
        ),
        # incoming attacks alert
        rx.cond(
            ColonyState.incoming_attacks.length() > 0,
            panel(
                rx.hstack(
                    pixel_img("/img/icon_attack.svg", 22),
                    rx.heading("적의 진군!", size="4", color=C_RED),
                    spacing="2",
                ),
                rx.foreach(
                    ColonyState.incoming_attacks,
                    lambda r: rx.hstack(
                        rx.text(r[0], size="2", weight="bold", color=C_RED),
                        rx.text("→", color=C_DIM, size="2"),
                        rx.text(r[1], size="2", color=C_TEXT),
                        rx.spacer(),
                        rx.text(r[2], size="1", color=C_RED),
                        spacing="2",
                        width="100%",
                    ),
                ),
                spacing="2",
            ),
        ),
        # marches
        panel(
            rx.hstack(pixel_img("/img/icon_map.svg", 20),
                      rx.heading("이동 중인 군세", size="4"), spacing="2"),
            rx.cond(
                ColonyState.marches_out.length() > 0,
                rx.vstack(
                    rx.foreach(ColonyState.marches_out, _march_row),
                    spacing="2",
                    width="100%",
                ),
                rx.text("이동 중인 부대가 없습니다.", size="2", color=C_DIM),
            ),
            spacing="3",
        ),
        # brood queue
        panel(
            rx.hstack(pixel_img("/img/u_worker.svg", 20),
                      rx.heading("육아방", size="4"), spacing="2"),
            rx.cond(
                ColonyState.brood_jobs.length() > 0,
                rx.vstack(
                    rx.foreach(
                        ColonyState.brood_jobs,
                        lambda j: rx.vstack(
                            rx.hstack(
                                pixel_img(j[0], 18),
                                rx.text(j[1], size="2", weight="bold"),
                                rx.spacer(),
                                rx.text(j[2].to(str), "마리 남음", size="1", color=C_DIM),
                                spacing="2",
                                width="100%",
                            ),
                            progress_bar(j[3]),
                            spacing="1",
                            width="100%",
                        ),
                    ),
                    spacing="2",
                    width="100%",
                ),
                rx.text("부화 중인 알이 없습니다.", size="2", color=C_DIM),
            ),
            rx.link("육아방으로 →", href="/brood", size="2", color=C_AMBER),
            spacing="3",
        ),
        # defense info
        panel(
            rx.hstack(pixel_img("/img/icon_shield.svg", 20),
                      rx.heading("방어 정보", size="4"), spacing="2"),
            rx.hstack(
                rx.text("가시문 보너스 +", ColonyState.defense_bonus_pct.to(str), "%",
                        size="2"),
                rx.spacer(),
                rx.text("숨긴 자원 ", ColonyState.hidden_res_str, size="2", color=C_GREEN),
                spacing="2",
                width="100%",
            ),
            rx.cond(
                ColonyState.army_summary.length() > 0,
                rx.flex(
                    rx.foreach(
                        ColonyState.army_summary,
                        lambda a: res_chip(a[0], a[1].to(str) + " ×" + a[2].to(str), C_TEXT),
                    ),
                    flex_wrap="wrap",
                    gap="8px",
                ),
                rx.text("주둔 개미가 없습니다! 육아방에서 병정을 키우세요.",
                        size="2", color=C_RED),
            ),
            spacing="3",
        ),
        on_load=[ColonyState.tick],
    )


def _res_detail_row(icon: str, label: str, amount: str, rate: str, color: str) -> rx.Component:
    return rx.hstack(
        pixel_img(icon, 24),
        rx.text(label, size="2", weight="bold", width="52px"),
        rx.text(g.fmt_num(float(amount)) if False else amount, size="2"),
        rx.spacer(),
        rx.text(rate, size="1", color=C_DIM),
        spacing="2",
        align="center",
        width="100%",
    )


def _fmt_amount(v) -> str:
    try:
        return g.fmt_num(float(v))
    except Exception:
        return str(v)
