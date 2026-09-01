"""Alliance page: create, join, manage, declare war."""

from __future__ import annotations

import datetime as dt

import reflex as rx
import sqlmodel
from sqlmodel import select

from .. import engine, gamedata as g
from ..components.layout import (
    C_DIM,
    C_RED,
    game_shell,
    page_title,
    panel,
    pixel_img,
)
from ..db import game_session
from ..game_state import GameState
from ..models import Alliance, Player, Report, War


class AllianceState(GameState):
    my_alliance_id: int = 0
    my_name: str = ""
    my_tag: str = ""
    my_desc: str = ""
    is_leader: bool = False
    members: list[list] = []  # [username, points, is_leader]
    open_list: list[list] = []  # [id, name, tag, member_count]
    wars: list[list] = []  # [enemy_name, enemy_tag, score_mine, score_theirs, ends_str, active]
    create_name: str = ""
    create_tag: str = ""

    @rx.event(background=True)
    async def load(self):
        async with self:
            if self._require_login():
                return
            self._sync_game()
            pid = self._player_id()

            with game_session() as s:
                player = s.get(Player, pid)
                aid = player.alliance_id
                self.my_alliance_id = aid or 0
                if aid:
                    a = s.get(Alliance, aid)
                    self.my_name = a.name
                    self.my_tag = a.tag
                    self.my_desc = a.description
                    self.is_leader = a.leader_id == pid
                    mems = s.exec(
                        select(Player).where(Player.alliance_id == aid)
                    ).all()
                    self.members = [
                        [
                            m.username,
                            round(engine.player_points(s, m.id), 1),
                            m.id == a.leader_id,
                        ]
                        for m in mems
                    ]
                    # wars involving my alliance
                    now = g.utc_now()
                    ws = s.exec(
                        select(War).where(
                            (War.alliance_a_id == aid) | (War.alliance_b_id == aid)
                        )
                    ).all()
                    rows = []
                    for w in ws[:10]:
                        other_id = (
                            w.alliance_b_id if w.alliance_a_id == aid else w.alliance_a_id
                        )
                        o = s.get(Alliance, other_id)
                        if o is None:
                            continue
                        score_me = w.score_a if w.alliance_a_id == aid else w.score_b
                        score_them = w.score_b if w.alliance_a_id == aid else w.score_a
                        rows.append(
                            [
                                o.name,
                                o.tag,
                                round(score_me, 2),
                                round(score_them, 2),
                                w.ends_at.strftime("%m/%d %H:%M"),
                                w.active and w.ends_at > now,
                            ]
                        )
                    self.wars = rows
                # alliance list for joining
                all_alliances = s.exec(select(Alliance)).all()
                lst = []
                for a in all_alliances:
                    if a.id == aid:
                        continue
                    cnt = len(
                        s.exec(
                            sqlmodel.select(Player).where(Player.alliance_id == a.id)
                        ).all()
                    )
                    lst.append([a.id, a.name, a.tag, cnt])
                self.open_list = lst
                s.commit()

    @rx.event(background=True)
    async def set_field(self, name: str, value: str):
        async with self:
            if name == "name":
                self.create_name = value
            else:
                self.create_tag = value

    @rx.event(background=True)
    async def create(self):
        async with self:
            if self._require_login():
                return
            name = self.create_name.strip()
            tag = self.create_tag.strip().upper()
            msg = ""
            with game_session() as s:
                player = s.get(Player, self._player_id())
                if player.alliance_id:
                    msg = "이미 동맹에 소속되어 있습니다."
                elif not (2 <= len(name) <= 24 and 2 <= len(tag) <= 5):
                    msg = "이름 2~24자, 태그 2~5자로 입력하세요."
                else:
                    dup = s.exec(
                        select(Alliance).where(
                            (Alliance.name == name) | (Alliance.tag == tag)
                        )
                    ).first()
                    if dup:
                        msg = "이름 또는 태그가 이미 사용 중입니다."
                    else:
                        a = Alliance(name=name, tag=tag, leader_id=player.id)
                        s.add(a)
                        s.flush()
                        player.alliance_id = a.id
                        s.add(player)
                        msg = f"동맹 [{tag}] {name} 창설!"
                s.commit()
            self.toast = msg
        yield AllianceState.load

    @rx.event(background=True)
    async def join(self, alliance_id: int):
        async with self:
            if self._require_login():
                return
            msg = ""
            with game_session() as s:
                player = s.get(Player, self._player_id())
                a = s.get(Alliance, alliance_id)
                if not a or player.alliance_id:
                    msg = "가입할 수 없습니다."
                else:
                    player.alliance_id = a.id
                    s.add(player)
                    msg = f"[{a.tag}] {a.name}에 가입했습니다!"
                s.commit()
            self.toast = msg
        yield GameState.refresh_game
        yield AllianceState.load

    @rx.event(background=True)
    async def leave(self):
        async with self:
            if self._require_login():
                return
            msg = ""
            with game_session() as s:
                player = s.get(Player, self._player_id())
                a = s.get(Alliance, player.alliance_id) if player.alliance_id else None
                if not a:
                    msg = "소속 동맹이 없습니다."
                elif a.leader_id == player.id:
                    members = s.exec(
                        select(Player).where(Player.alliance_id == a.id)
                    ).all()
                    others = [m for m in members if m.id != player.id]
                    if others:
                        msg = "리더는 위임 후 탈퇴하세요. (멤버가 남아 있습니다)"
                    else:
                        player.alliance_id = None
                        s.add(player)
                        s.delete(a)
                        msg = "동맹을 해산했습니다."
                else:
                    player.alliance_id = None
                    s.add(player)
                    msg = "동맹을 탈퇴했습니다."
                s.commit()
            self.toast = msg
        yield GameState.refresh_game
        yield AllianceState.load

    @rx.event(background=True)
    async def declare_war(self, target_id: int):
        async with self:
            if self._require_login():
                return
            msg = ""
            with game_session() as s:
                me = s.get(Player, self._player_id())
                mine = s.get(Alliance, me.alliance_id) if me.alliance_id else None
                if not mine or mine.leader_id != me.id:
                    msg = "동맹 리더만 선전포고할 수 있습니다."
                else:
                    target = s.get(Alliance, target_id)
                    existing = engine.war_between(s, mine.id, target.id)
                    if existing:
                        msg = "이미 교전 중입니다."
                    elif not engine.consume_energy(
                        session=s, player=me, amount=g.COST_DECLARE_WAR
                    ):
                        msg = f"행동 에너지가 부족합니다 ({int(g.COST_DECLARE_WAR)} 필요)."
                    else:
                        w = War(
                            alliance_a_id=mine.id,
                            alliance_b_id=target.id,
                            declared_at=g.utc_now(),
                            ends_at=g.utc_now() + dt.timedelta(hours=g.WAR_DURATION_HOURS),
                            active=True,
                        )
                        s.add(w)
                        # notify all members of both alliances
                        for side in (mine.id, target.id):
                            for m in s.exec(
                                sqlmodel.select(Player).where(Player.alliance_id == side)
                            ).all():
                                rep = Report(
                                    player_id=m.id,
                                    kind="system",
                                    title=(
                                        f"⚔ [{mine.tag}]가 [{target.tag}]에게 선전포고!"
                                    ),
                                )
                                rep.set_body(
                                    {
                                        "text": (
                                            f"{g.WAR_DURATION_HOURS}시간 동안 두 동맹은 교전 상태입니다. "
                                            "교전 중 공격 시 전투력 +25%이며 격추 전과가 점수화됩니다."
                                        )
                                    }
                                )
                                s.add(rep)
                        msg = f"[{target.tag}]에게 선전포고! ({g.WAR_DURATION_HOURS}시간)"
                s.commit()
            self.toast = msg
        yield AllianceState.load


def _member_row(m) -> rx.Component:
    return rx.hstack(
        rx.cond(m[2], pixel_img("/img/queen.svg", 18), rx.box(width="18px")),
        rx.text(m[0], size="2", weight="bold"),
        rx.spacer(),
        rx.text(m[1].to(str), "점", size="1", color=C_DIM),
        spacing="2",
        width="100%",
        padding_y="4px",
    )


def _open_row(a) -> rx.Component:
    return rx.hstack(
        rx.badge(a[2], color_scheme="amber", variant="surface"),
        rx.text(a[1], size="2"),
        rx.text(a[3].to(str), "명", size="1", color=C_DIM),
        rx.spacer(),
        rx.button("가입", size="1", variant="surface",
                  on_click=lambda: AllianceState.join(a[0])),
        spacing="2",
        align="center",
        width="100%",
        padding_y="4px",
    )


def _war_row(w) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.badge(w[1], color_scheme="red", variant="surface"),
            rx.text(w[0], size="2", weight="bold", color=C_RED),
            rx.cond(
                w[5],
                rx.badge("교전 중", color_scheme="red"),
                rx.badge("종료", color_scheme="gray"),
            ),
            spacing="2",
        ),
        rx.text(
            "전과 ", w[2].to(str), " : ", w[3].to(str),
            " — 종료 예정 ", w[4],
            size="1",
            color=C_DIM,
        ),
        spacing="1",
        width="100%",
    )


def alliance_page() -> rx.Component:
    return game_shell(
        "/more/alliance",
        page_title("동맹", "/img/icon_flag.svg"),
        rx.cond(
            AllianceState.my_alliance_id > 0,
            panel(
                rx.hstack(
                    rx.badge(AllianceState.my_tag, color_scheme="amber",
                             variant="surface"),
                    rx.heading(AllianceState.my_name, size="4"),
                    spacing="2",
                ),
                rx.text("멤버", size="1", color=C_DIM),
                rx.vstack(
                    rx.foreach(AllianceState.members, _member_row),
                    spacing="1",
                    width="100%",
                ),
                rx.button("탈퇴하기", variant="surface", size="2",
                          on_click=AllianceState.leave),
                spacing="3",
            ),
            panel(
                rx.heading("새 동맹 창설", size="4"),
                rx.hstack(
                    rx.input(
                        placeholder="동맹 이름",
                        value=AllianceState.create_name,
                        flex="1",
                        on_change=lambda v: AllianceState.set_field("name", v),
                    ),
                    rx.input(
                        placeholder="태그",
                        value=AllianceState.create_tag,
                        width="90px",
                        on_change=lambda v: AllianceState.set_field("tag", v),
                    ),
                    spacing="2",
                    width="100%",
                ),
                rx.button("창설", color_scheme="amber", width="100%", size="2",
                          on_click=AllianceState.create),
                spacing="3",
            ),
        ),
        panel(
            rx.heading("동맹 목록", size="4"),
            rx.cond(
                AllianceState.open_list.length() > 0,
                rx.vstack(
                    rx.foreach(AllianceState.open_list, _open_row),
                    spacing="1",
                    width="100%",
                ),
                rx.text("다른 동맹이 아직 없습니다.", size="2", color=C_DIM),
            ),
            spacing="3",
        ),
        rx.cond(
            AllianceState.is_leader,
            panel(
                rx.heading("선전포고", size="4"),
                rx.text("다른 동맹에 전쟁을 선포하면 72시간 동안 교전 상태가 됩니다. "
                        "교전 중 상대 동맹 공격 시 전투력 +25%, 격추 전과가 점수화됩니다.",
                        size="1", color=C_DIM),
                rx.cond(
                    AllianceState.open_list.length() > 0,
                    rx.vstack(
                        rx.foreach(
                            AllianceState.open_list,
                            lambda a: rx.hstack(
                                rx.badge(a[2], variant="surface", color_scheme="red"),
                                rx.text(a[1], size="2"),
                                rx.spacer(),
                                rx.button(
                                    "선전포고", size="1", color_scheme="red",
                                    variant="surface",
                                    on_click=lambda: AllianceState.declare_war(a[0]),
                                ),
                                spacing="2",
                                width="100%",
                                padding_y="4px",
                            ),
                        ),
                        spacing="1",
                        width="100%",
                    ),
                    rx.text("선포 가능한 동맹이 없습니다.", size="2", color=C_DIM),
                ),
                rx.badge(f"⚡ {int(g.COST_DECLARE_WAR)}", variant="surface"),
                spacing="3",
            ),
        ),
        rx.cond(
            AllianceState.wars.length() > 0,
            panel(
                rx.heading("전쟁 현황", size="4"),
                rx.vstack(
                    rx.foreach(AllianceState.wars, _war_row),
                    spacing="3",
                    width="100%",
                ),
                spacing="3",
            ),
        ),
        on_load=[AllianceState.load],
    )
