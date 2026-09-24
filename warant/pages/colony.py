"""Colony overview: resources, queues, marches at a glance."""

from __future__ import annotations

import reflex as rx
from sqlmodel import select

from .. import engine
from .. import gamedata as g
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
    total_army: int = 0
    army_tier_gif: str = "/img/colony_working_t1.gif"
    army_tier_title: str = "🌱 소형 군락"
    army_tier_desc: str = "일개미들이 버섯과 이슬을 분주히 나르고 있습니다."

    def _sync_page_data(self, s, pid: int, nest):
        player_nests = engine.nests_of(s, pid)
        self.nest_name = nest.name
        self.nest_coord = f"{nest.x}:{nest.y}"
        levels = engine.building_levels(s, nest.id)

        # brood queue for this nest
        jobs = s.exec(
            select(BroodJob).where(BroodJob.nest_id == nest.id)
        ).all()
        out = []
        for j in jobs:
            unit_sec = max(j.unit_seconds, 0.001)
            elapsed = max(0.0, (g.utc_now() - j.started_at).total_seconds())
            cur_progress = elapsed % unit_sec
            pct = int(min(100, max(0, cur_progress / unit_sec * 100)))
            out.append(
                [
                    f"/img/u_{j.unit_key}.svg",
                    g.UNITS[j.unit_key].name,
                    j.count,
                    pct,
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

        total_army = sum(army.get(k, 0) for k in g.UNIT_ORDER)
        self.total_army = total_army

        if total_army < 25:
            self.army_tier_gif = "/img/colony_working_t1.gif"
            self.army_tier_title = "🌱 소형 군락"
            self.army_tier_desc = f"군세 {total_army}마리 — 일개미들이 둥지를 넓히며 자원을 나르고 있습니다."
        elif total_army < 100:
            self.army_tier_gif = "/img/colony_working_t2.gif"
            self.army_tier_title = "🌿 번영하는 둥지"
            self.army_tier_desc = f"군세 {total_army}마리 — 분주한 일개미 행렬과 병정개미 경계조가 둥지를 지킵니다."
        elif total_army < 300:
            self.army_tier_gif = "/img/colony_working_t3.gif"
            self.army_tier_title = "🏰 거대 왕국"
            self.army_tier_desc = f"군세 {total_army}마리 — 강력한 대형병정과 정예 군세가 왕국을 수호합니다."
        else:
            self.army_tier_gif = "/img/colony_working_t4.gif"
            self.army_tier_title = "👑 제국 군세"
            self.army_tier_desc = f"군세 {total_army}마리 — 거대 대형병정과 비행개미 등 제국급 대군세가 위용을 떨칩니다."

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

    @rx.event(background=True)
    async def tick(self):
        async with self:
            if self._require_login():
                return
            self._sync_game()


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
        # Colony status panel (with animated pixel-art working ant scene)
        panel(
            page_title("둥지 현황", "/img/queen.svg"),
            rx.hstack(
                rx.text(GameState.points.to(str), color=C_AMBER, size="3", weight="bold"),
                rx.text("점수", color=C_DIM, size="1"),
                rx.spacer(),
                rx.badge(ColonyState.nest_coord, variant="surface", color_scheme="amber"),
                rx.text(GameState.nests_list.length().to(str), "개 둥지", color=C_DIM, size="2"),
                spacing="2",
                align="center",
            ),
            # Pixel-art working ant colony scene
            rx.box(
                rx.image(
                    src=ColonyState.army_tier_gif,
                    width="100%",
                    height="auto",
                    style={
                        "image_rendering": "pixelated",
                        "border_radius": "8px",
                        "border": f"1px solid {C_BORDER}",
                    },
                ),
                width="100%",
            ),
            rx.hstack(
                rx.badge(ColonyState.army_tier_title, color_scheme="amber", variant="surface", size="2"),
                rx.spacer(),
                rx.text("주둔 군세 ", rx.text(ColonyState.total_army.to(str), weight="bold", color=C_GREEN, as_="span"), "마리", size="2", color=C_DIM),
                width="100%",
                align="center",
            ),
            rx.text(ColonyState.army_tier_desc, size="1", color=C_DIM),
            rx.divider(border_color=C_BORDER),
            rx.hstack(
                rx.text("저장고 사용률", size="1", color=C_DIM),
                rx.spacer(),
                rx.text(ColonyState.granary_pct.to(str), "%", size="1", color=C_AMBER, weight="bold"),
                width="100%",
                align="center",
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
                    rx.link("건설 보기 →", href="/buildings", size="2", color=C_AMBER),
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
                    rx.link("연구 보기 →", href="/more/research", size="2", color=C_AMBER),
                    spacing="2",
                    flex="1", min_width="45%",
                ),
                panel(
                    rx.hstack(pixel_img("/img/b_research_chamber.svg", 20),
                              rx.text("연구 대기 없음", size="2", weight="bold", color=C_DIM), spacing="2"),
                    rx.link("연구 시작하기 →", href="/more/research", size="2", color=C_AMBER),
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
