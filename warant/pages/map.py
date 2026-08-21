"""World map & marches: attack, scout, hunt, transfer, deploy."""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

import reflex as rx
from sqlmodel import select

from .. import engine, gamedata as g
from ..components.layout import (
    C_AMBER,
    C_BORDER,
    C_DIM,
    C_RED,
    game_shell,
    page_title,
    panel,
    pixel_img,
)
from ..db import game_session
from ..game_state import GameState
from ..models import March, Nest, Player

VIEW_R = 3  # 7x7 grid


@dataclass
class Cell:
    x: int
    y: int
    kind: str
    label: str


class MapState(GameState):
    cx: int = 50
    cy: int = 50
    cells: list[list[Cell]] = []
    # selected cell
    sx: int = -1
    sy: int = -1
    s_kind: str = ""
    s_label: str = ""
    s_owner: str = ""
    s_protected: bool = False
    s_nest_id: int = 0
    # march form
    unit_inputs: list[list] = []  # [key, name, count_str]
    cargo_food: str = "0"
    cargo_water: str = "0"
    march_eta: str = ""
    my_nest_ids: list[int] = []

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
                if self.cx == 0 and self.cy == 0:
                    self.cx, self.cy = nest.x, nest.y
                movable = [[k, g.UNITS[k].name, "0"] for k in g.UNIT_ORDER]
                self.unit_inputs = movable
                self.my_nest_ids = [n.id for n in engine.nests_of(s, pid)]
            yield MapState.refresh_cells

    @rx.event(background=True)
    async def pan(self, dx: int, dy: int):
        async with self:
            self.cx = max(0, min(g.MAP_SIZE - 1, self.cx + dx))
            self.cy = max(0, min(g.MAP_SIZE - 1, self.cy + dy))
        yield MapState.refresh_cells

    @rx.event(background=True)
    async def refresh_cells(self):
        async with self:
            if self._require_login():
                return
            with game_session() as s:
                nests = {
                    (n.x, n.y): n
                    for n in s.exec(
                        select(Nest).where(
                            Nest.x >= self.cx - VIEW_R,
                            Nest.x <= self.cx + VIEW_R,
                            Nest.y >= self.cy - VIEW_R,
                            Nest.y <= self.cy + VIEW_R,
                        )
                    ).all()
                }
                pid = self._player_id()
                rows = []
                for y in range(self.cy - VIEW_R, self.cy + VIEW_R + 1):
                    row = []
                    for x in range(self.cx - VIEW_R, self.cx + VIEW_R + 1):
                        kind, label = ("wild", "")
                        n = nests.get((x, y))
                        if n is not None and 0 <= x < g.MAP_SIZE and 0 <= y < g.MAP_SIZE:
                            if n.player_id == pid:
                                kind = "own"
                                label = n.name
                            else:
                                kind = "enemy"
                                owner = s.get(Player, n.player_id)
                                label = f"{owner.username}의 {n.name}" if owner else n.name
                        elif not (0 <= x < g.MAP_SIZE and 0 <= y < g.MAP_SIZE):
                            kind = "void"
                        row.append(Cell(x=x, y=y, kind=kind, label=label))
                    rows.append(row)
                self.cells = rows

    @rx.event(background=True)
    async def select_cell(self, x: int, y: int):
        async with self:
            if self._require_login():
                return
            pid = self._player_id()
            self.sx, self.sy = x, y
            with game_session() as s:
                nest_obj = s.exec(
                    select(Nest).where(Nest.x == x, Nest.y == y)
                ).first()
                if nest_obj is None:
                    self.s_kind = "hunt" if 0 <= x < g.MAP_SIZE else "void"
                    self.s_label = "야생 사냥터"
                    self.s_owner = ""
                    self.s_protected = False
                    self.s_nest_id = 0
                elif nest_obj.player_id == pid:
                    self.s_kind = "own"
                    self.s_label = nest_obj.name
                    self.s_owner = "내 둥지"
                    self.s_protected = False
                    self.s_nest_id = nest_obj.id
                else:
                    owner = s.get(Player, nest_obj.player_id)
                    self.s_kind = "enemy"
                    self.s_label = nest_obj.name
                    self.s_owner = owner.username if owner else "?"
                    self.s_protected = engine.is_protected(s, owner)
                    self.s_nest_id = nest_obj.id
            # ETA preview using scout speed default
            yield MapState.update_eta

    @rx.event
    def update_eta(self):
        units = {}
        for k, v in self.unit_inputs:
            try:
                c = int(v[2] or 0)
            except (ValueError, IndexError):
                c = 0
            if c > 0:
                units[k[0]] = c
        if not units or self.sx < 0:
            self.march_eta = ""
        else:
            slow = min(g.UNITS[k].speed for k in units)
            self.march_eta = f"최속 부대 {slow}칸/분"

    @rx.event(background=True)
    async def set_unit_input(self, key: str, value: str):
        async with self:
            self.unit_inputs = [
                [row[0], row[1], value] if row[0] == key else row
                for row in self.unit_inputs
            ]

    @rx.event
    def set_cargo_food(self, v: str):
        self.cargo_food = v

    @rx.event
    def set_cargo_water(self, v: str):
        self.cargo_water = v

    @rx.event(background=True)
    async def send_march(self, kind: str):
        async with self:
            if self._require_login():
                return
            pid = self._player_id()
            msg = ""
            with game_session() as s:
                player = s.get(Player, pid)
                home = self._nest(s)
                if home is None:
                    return
                if self.sx < 0:
                    msg = "먼저 지도에서 목표 지점을 선택하세요."
                else:
                    units = {}
                    for row in self.unit_inputs:
                        try:
                            c = int(row[2] or 0)
                        except (ValueError, IndexError):
                            c = 0
                        if c > 0:
                            units[row[0]] = c
                    if not units:
                        msg = "보낼 개미를 입력하세요."
                    elif any(k in g.DEFENSE_ORDER for k in units):
                        msg = "방어 시설은 이동할 수 없습니다."
                    else:
                        ok = False
                        if kind == g.MARCH_HUNT:
                            if s.exec(
                                select(Nest).where(Nest.x == self.sx, Nest.y == self.sy)
                            ).first():
                                msg = "사냥은 빈 야생 땅에만 가능합니다."
                            else:
                                ok = True
                        elif kind in (g.MARCH_TRANSFER, g.MARCH_DEPLOY):
                            target = s.get(Nest, self.s_nest_id)
                            if (
                                self.s_kind != "own"
                                or target is None
                                or target.player_id != pid
                            ):
                                msg = "내 둥지로만 가능합니다."
                            elif target.id == home.id:
                                msg = "같은 둥지입니다."
                            elif kind == g.MARCH_TRANSFER and (
                                float(self.cargo_food or 0) <= 0
                                and float(self.cargo_water or 0) <= 0
                            ):
                                msg = "이송할 자원을 입력하세요."
                            else:
                                ok = True
                        elif kind in (g.MARCH_ATTACK, g.MARCH_SCOUT):
                            target = s.get(Nest, self.s_nest_id)
                            towner = (
                                s.get(Player, target.player_id) if target else None
                            )
                            if towner is None or towner.id == pid:
                                msg = "대상을 선택하세요."
                            elif engine.is_protected(s, towner):
                                msg = "신규 보호 중인 콜로니는 공격할 수 없습니다."
                            elif towner.alliance_id and towner.alliance_id == player.alliance_id:
                                msg = "같은 동맹을 공격할 수 없습니다."
                            else:
                                ok = True
                        if ok:
                            cost = {
                                g.MARCH_ATTACK: g.COST_MARCH_ATTACK,
                                g.MARCH_SCOUT: g.COST_MARCH_SCOUT,
                                g.MARCH_HUNT: g.COST_MARCH_HUNT,
                                g.MARCH_TRANSFER: g.COST_MARCH_TRANSFER,
                                g.MARCH_DEPLOY: g.COST_MARCH_DEPLOY,
                            }[kind]
                            have_units = engine.army_at(s, home.id)
                            short = {
                                k: v
                                for k, v in units.items()
                                if have_units.get(k, 0) < v
                            }
                            if short:
                                msg = f"개미 부족: {', '.join(short)}"
                            elif not engine.consume_energy(
                                session=s, player=player, amount=cost
                            ):
                                msg = f"행동 에너지가 부족합니다 ({int(cost)} 필요)."
                            else:
                                if kind == g.MARCH_TRANSFER:
                                    cf = max(0.0, float(self.cargo_food or 0))
                                    cw = max(0.0, float(self.cargo_water or 0))
                                    cf = min(cf, home.res_food)
                                    cw = min(cw, home.res_water)
                                    home.res_food -= cf
                                    home.res_water -= cw
                                    s.add(home)
                                else:
                                    cf = cw = 0.0
                                if not engine.remove_army(s, home.id, units):
                                    msg = "개미를 떼어낼 수 없습니다."
                                else:
                                    research = engine.research_levels(s, pid)
                                    slow = min(g.UNITS[k].speed for k in units)
                                    dist = math.hypot(
                                        self.sx - home.x, self.sy - home.y
                                    )
                                    t = g.travel_seconds(
                                        dist,
                                        slow,
                                        research.get("tunneling", 0),
                                    )
                                    m = March(
                                        player_id=pid,
                                        from_nest_id=home.id,
                                        kind=kind,
                                        tx=self.sx,
                                        ty=self.sy,
                                        hx=home.x,
                                        hy=home.y,
                                        target_nest_id=self.s_nest_id or None,
                                        depart_at=g.utc_now(),
                                        arrive_at=g.utc_now() + dt.timedelta(seconds=t),
                                        cargo_food=cf,
                                        cargo_water=cw,
                                    )
                                    m.set_units(units)
                                    s.add(m)
                                    msg = (
                                        f"{g.MARCH_NAMES[kind]} 진군 시작! "
                                        f"(도착 {g.fmt_duration(t)}, "
                                        f"에너지 -{int(cost)})"
                                    )
                        s.commit()
            self.toast = msg
        yield GameState.refresh_game


def _cell_bg(kind) -> str:
    return rx.match(
        kind,
        ("own", C_AMBER),
        ("enemy", C_RED),
        ("wild", "#3a4a2c"),
        ("void", "#0d0a08"),
        "#241c16",
    )


def _cell_button(cell: Cell) -> rx.Component:
    return rx.button(
        rx.cond(
            (cell.kind == "own") | (cell.kind == "enemy"),
            rx.cond(
                cell.kind == "own",
                pixel_img("/img/queen.svg", 20),
                pixel_img("/img/w_spider.svg", 20),
            ),
            rx.box(),
        ),
        width="44px",
        height="44px",
        background=_cell_bg(cell.kind),
        border=f"1px solid {C_BORDER}",
        border_radius="4px",
        padding="0",
        on_click=lambda: MapState.select_cell(cell.x, cell.y),
        title=cell.label,
    )


def _map_grid() -> rx.Component:
    return rx.vstack(
        rx.foreach(MapState.cells, lambda row:
                   rx.hstack(
                       rx.foreach(row, _cell_button),
                       gap="2px",
                       justify_content="center",
                   )),
        gap="2px",
        align="center",
    )


KIND_LABEL = {"own": "내 둥지", "enemy": "적 둥지", "hunt": "야생 사냥터", "void": ""}


def _selection_panel() -> rx.Component:
    return rx.cond(
        MapState.sx >= 0,
        panel(
            rx.hstack(
                rx.heading(
                    "[",
                    MapState.sx.to(str),
                    ":",
                    MapState.sy.to(str),
                    "] ",
                    MapState.s_label,
                    size="4",
                ),
                spacing="2",
            ),
            rx.text(MapState.s_owner, size="1", color=C_DIM),
            rx.cond(
                (MapState.s_kind == "enemy") & MapState.s_protected,
                rx.callout(rx.text("신규 보호 중 — 공격 불가", size="1"),
                           color_scheme="gray", width="100%"),
            ),
            _march_buttons(),
            spacing="3",
        ),
        panel(
            rx.text("지도를 눌러 목표를 선택하세요. 사냥터는 초록색 칸입니다.",
                    size="2", color=C_DIM),
        ),
    )


def _march_buttons() -> rx.Component:
    return rx.vstack(
        rx.cond(
            MapState.s_kind == "enemy",
            rx.hstack(
                rx.button(
                    "정찰", flex="1", color_scheme="blue",
                    on_click=lambda: MapState.send_march(g.MARCH_SCOUT),
                    size="3",
                ),
                rx.button(
                    "공격", flex="1", color_scheme="red",
                    on_click=lambda: MapState.send_march(g.MARCH_ATTACK),
                    size="3",
                ),
                spacing="2",
                width="100%",
            ),
        ),
        rx.cond(
            MapState.s_kind == "own",
            rx.hstack(
                rx.button(
                    "이송", flex="1", color_scheme="grass",
                    on_click=lambda: MapState.send_march(g.MARCH_TRANSFER),
                    size="3",
                ),
                rx.button(
                    "주둔", flex="1", variant="surface",
                    on_click=lambda: MapState.send_march(g.MARCH_DEPLOY),
                    size="3",
                ),
                spacing="2",
                width="100%",
            ),
        ),
        rx.cond(
            MapState.s_kind == "hunt",
            rx.button(
                "사냥 보내기", width="100%", color_scheme="green",
                on_click=lambda: MapState.send_march(g.MARCH_HUNT), size="3",
            ),
        ),
        spacing="2",
        width="100%",
    )


def _unit_send_row(row) -> rx.Component:
    key, name, val = row[0], row[1], row[2]
    return rx.hstack(
        pixel_img("/img/u_" + key.to(str) + ".svg", 22),
        rx.text(name, size="2", width="70px"),
        rx.input(
            value=val,
            width="80px",
            type_="number",
            min_=0,
            on_change=lambda v: MapState.set_unit_input(key, v),
        ),
        spacing="2",
        align="center",
        width="100%",
    )


def map_page() -> rx.Component:
    return game_shell(
        "/map",
        page_title("세계 지도", "/img/icon_map.svg"),
        panel(
            _map_grid(),
            rx.hstack(
                rx.button("←", on_click=lambda: MapState.pan(-1, 0), size="2"),
                rx.button("↑", on_click=lambda: MapState.pan(0, -1), size="2"),
                rx.button("↓", on_click=lambda: MapState.pan(0, 1), size="2"),
                rx.button("→", on_click=lambda: MapState.pan(1, 0), size="2"),
                rx.spacer(),
                rx.text(
                    "중심 [",
                    MapState.cx.to(str),
                    ":",
                    MapState.cy.to(str),
                    "]",
                    size="1",
                    color=C_DIM,
                ),
                spacing="2",
                align="center",
                width="100%",
            ),
            spacing="3",
        ),
        _selection_panel(),
        panel(
            rx.heading("출발 군세", size="4"),
            rx.text("보낼 개미 수를 입력하세요. 가장 느린 개미 속도로 이동합니다.",
                    size="1", color=C_DIM),
            rx.vstack(
                rx.foreach(MapState.unit_inputs, _unit_send_row),
                spacing="2",
                width="100%",
            ),
            rx.cond(
                MapState.s_kind == "own",
                rx.hstack(
                    pixel_img("/img/res_food.svg", 18),
                    rx.input(value=MapState.cargo_food, placeholder="먹이",
                             width="100%", type_="number",
                             on_change=MapState.set_cargo_food),
                    pixel_img("/img/res_water.svg", 18),
                    rx.input(value=MapState.cargo_water, placeholder="물",
                             width="100%", type_="number",
                             on_change=MapState.set_cargo_water),
                    spacing="2",
                    width="100%",
                    align="center",
                ),
            ),
            spacing="3",
        ),
        on_load=[MapState.load],
    )
