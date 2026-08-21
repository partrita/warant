"""Reports page: battle/scout/hunt/system messages."""

from __future__ import annotations

from dataclasses import dataclass, field

import reflex as rx
from sqlmodel import select

from .. import gamedata as g
from ..components.layout import (
    C_AMBER,
    C_BLUE,
    C_DIM,
    C_GREEN,
    C_RED,
    C_TEXT,
    game_shell,
    page_title,
    panel,
    pixel_img,
)
from ..db import game_session
from ..game_state import GameState
from ..models import Report

KIND_ICON_SEQ = [
    ("battle", "/img/icon_attack.svg"),
    ("scout", "/img/icon_scout.svg"),
    ("hunt", "/img/icon_hunt.svg"),
    ("transfer", "/img/icon_transfer.svg"),
    ("deploy", "/img/icon_transfer.svg"),
    ("system", "/img/queen.svg"),
]

KIND_COLOR = {
    "battle": C_RED,
    "scout": C_BLUE,
    "hunt": C_GREEN,
}


def _kind_icon(kind) -> rx.Component:
    return rx.match(
        kind,
        *[(k, pixel_img(icon, 26)) for k, icon in KIND_ICON_SEQ],
        pixel_img("/img/icon_report.svg", 26),
    )


def _kind_color(kind):
    return rx.match(
        kind,
        ("battle", C_RED),
        ("scout", C_BLUE),
        ("hunt", C_GREEN),
        C_AMBER,
    )


def _unit_label(k) -> str:
    if k in g.UNITS:
        return g.UNITS[k].name
    if k in g.WILD_INSECTS:
        return g.WILD_INSECTS[k].name
    return k


def _fmt_losses(d: dict) -> str:
    parts = [f"{_unit_label(k)} ×{v}" for k, v in d.items() if v]
    return ", ".join(parts) if parts else "없음"


def _battle_lines(b: dict, role: str) -> list[str]:
    won = b.get("winner") == ("attacker" if role == "attacker" else "defender")
    lines = ["결과: " + ("승리!" if won else "패배…")]
    atk_l = _fmt_losses(b.get("atk_losses", {}))
    def_l = _fmt_losses(b.get("def_losses", {}))
    if role == "attacker":
        lines.append(f"내 손실: {atk_l}")
        lines.append(f"적 손실: {def_l}")
        lf, lw = b.get("loot_food", 0), b.get("loot_water", 0)
        if lf or lw:
            lines.append(f"약탈: 먹이 {lf:,}, 물 {lw:,}")
    else:
        lines.append(f"방어 손실: {def_l}")
        lines.append(f"적 손실: {atk_l}")
        if b.get("war"):
            lines.append("동맹 전쟁 중 — 전과가 기록되었습니다.")
    n_rounds = len(b.get("rounds", []))
    lines.append(f"{n_rounds}라운드 전투")
    return lines


def _body_lines(kind: str, b: dict) -> list[str]:
    role = b.get("role", "attacker")
    try:
        if kind == "battle":
            return _battle_lines(b, role)
        if kind == "scout":
            if not b.get("success", True):
                return [
                    f"정찰 실패! 정찰개미 {_fmt_losses({'scout': b.get('caught', 0)})}",
                    "감시초소와 정찰개미에게 발각되었습니다.",
                ]
            lines = []
            owner = b.get("owner", "?")
            lines.append(f"대상 여왕: {owner}")
            if b.get("res_food") is not None and b.get("res_food") != "":
                lines.append(
                    f"자원: 먹이 약 {float(b['res_food']):,.0f}, "
                    f"물 약 {float(b.get('res_water', 0)):,.0f}"
                )
            bl = b.get("buildings") or {}
            if bl:
                lines.append(
                    "시설: "
                    + ", ".join(f"{g.BUILDINGS[k].name} {v}" for k, v in bl.items())
                )
            am = b.get("army") or {}
            if am:
                lines.append("주둔군: " + ", ".join(f"{_unit_label(k)} ×{v}" for k, v in am.items()))
            elif b.get("partial"):
                pass
            if b.get("partial"):
                lines.append("(일부 정보만 획득)")
            return lines
        if kind == "hunt":
            lines = []
            wild = b.get("wild") or {}
            wl = b.get("wild_losses") or {}
            my = b.get("losses") or {}
            if b.get("wiped"):
                lines.append("사냥 부대가 전멸했습니다…")
                lines.append(f"마주친 벌레: {_fmt_losses({k: v for k, v in wild.items()})}")
            else:
                lines.append(
                    f"수확: 먹이 {b.get('food', 0):,}, 물 {b.get('water', 0):,}"
                )
                lines.append(f"내 손실: {_fmt_losses(my)}")
                killed = {k: v for k, v in wl.items() if v}
                if killed:
                    lines.append(f"처치한 벌레: {_fmt_losses(killed)}")
            return lines
        if kind == "transfer":
            return [
                f"{b.get('to','?')} ({b.get('coord','')}) 로 "
                f"먹이 {b.get('food',0):,.0f}, 물 {b.get('water',0):,.0f} 도착"
            ]
        if kind == "deploy":
            units = b.get("units") or {}
            return [
                f"{b.get('to','?')} ({b.get('coord','')}) 에 주둔: "
                + ", ".join(f"{_unit_label(k)} ×{v}" for k, v in units.items())
            ]
        if kind == "system":
            t = b.get("text", "")
            c = b.get("coord", "")
            return [t + (f" 위치 [{c}]" if c else "")]
    except Exception:
        pass
    return []


@dataclass
class ReportCard:
    rid: int
    kind: str
    title: str
    created: str
    lines: list[str] = field(default_factory=list)


class ReportsState(GameState):
    rows: list[ReportCard] = []

    @rx.event(background=True)
    async def load(self):
        await GameState.refresh_game()
        async with self:
            if self._require_login():
                return
            with game_session() as s:
                reps = s.exec(
                    select(Report)
                    .where(Report.player_id == self._player_id())
                    .order_by(Report.created_at.desc())  # type: ignore
                    .limit(50)
                ).all()
                rows = []
                for r in reps:
                    lines = _body_lines(r.kind, r.body())
                    rows.append(
                        ReportCard(
                            rid=r.id,
                            kind=r.kind,
                            title=r.title,
                            created=r.created_at.strftime("%m/%d %H:%M"),
                            lines=lines,
                        )
                    )
                    if not r.is_read:
                        r.is_read = True
                        s.add(r)
                self.rows = rows
                s.commit()


def _report_card(card: ReportCard) -> rx.Component:
    return panel(
        rx.hstack(
            _kind_icon(card.kind),
            rx.vstack(
                rx.hstack(
                    rx.text(card.title, size="2", weight="bold",
                            color=_kind_color(card.kind)),
                    rx.badge(card.created, variant="surface"),
                    spacing="2",
                ),
                spacing="1",
                align="start",
            ),
            spacing="3",
            align="center",
            width="100%",
        ),
        rx.foreach(
            card.lines,
            lambda line: rx.text(line, size="2", color=C_TEXT),
        ),
        spacing="2",
    )


def reports_page() -> rx.Component:
    return game_shell(
        "/more/reports",
        page_title("보고서", "/img/icon_report.svg"),
        rx.cond(
            ReportsState.rows.length() > 0,
            rx.vstack(
                rx.foreach(ReportsState.rows, _report_card),
                spacing="3",
                width="100%",
            ),
            panel(rx.text("아직 보고서가 없습니다.", size="2", color=C_DIM)),
        ),
        on_load=[ReportsState.load],
    )
