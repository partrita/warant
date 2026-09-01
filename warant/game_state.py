"""Shared game state: active nest selection, resource snapshot, guards."""

from __future__ import annotations

import reflex as rx
from sqlmodel import select

from . import engine, gamedata as g
from .auth_state import AuthState
from .db import game_session
from .models import ConstructionJob, Nest, Player, ResearchJob


class GameState(AuthState):
    """Base for all in-game pages. Requires a logged-in player."""

    nest_id: int = 0  # currently viewed nest (0 = main nest)
    # Resource bar (refreshed by refresh_game)
    res_food: float = 0
    res_water: float = 0
    cap_food: float = 0
    prod_food: float = 0
    prod_water: float = 0
    energy: float = 100
    points: float = 0
    # Pre-formatted display strings (safe for direct rendering)
    food_disp: str = "0"
    water_disp: str = "0"
    food_rate_disp: str = "0/h"
    water_rate_disp: str = "0/h"
    energy_disp: str = "100/100"
    toast: str = ""
    nests_list: list[list] = []  # [nest_id, name, x, y, is_main]
    has_construction: bool = False
    construction_done_pct: int = 0
    construction_label: str = ""
    construction_eta: str = ""
    has_research: bool = False
    research_done_pct: int = 0
    research_label: str = ""
    research_eta: str = ""

    def _require_login(self) -> bool:
        return not self._player_id()

    def _nest(self, session) -> Nest | None:
        pid = self._player_id()
        my_nests = engine.nests_of(session, pid)
        if not my_nests:
            return None
        if self.nest_id:
            for n in my_nests:
                if n.id == self.nest_id:
                    return n
        return my_nests[0]

    @rx.event
    def switch_nest(self, nest_id: str):
        self.nest_id = int(nest_id)
        return [GameState.clear_toast, GameState.refresh_game]

    @rx.event
    def show_toast(self, msg: str):
        self.toast = msg

    @rx.event
    def clear_toast(self):
        self.toast = ""

    @staticmethod
    def _progress(start, end) -> tuple[int, str]:
        now_ts = g.utc_now().timestamp()
        total = max(end.timestamp() - start.timestamp(), 1)
        done = min(max(now_ts - start.timestamp(), 0), total)
        eta = end.timestamp() - now_ts
        return int(done / total * 100), g.fmt_duration(eta)

    def _sync_game(self, session=None):
        """Internal synchronous helper to sync and refresh game data for current state."""
        if self._require_login():
            return
        pid = self._player_id()

        def _do_sync(s):
            player = s.get(Player, pid)
            if not player:
                return
            engine.process_player(s, player)

            rjob = s.exec(
                select(ResearchJob).where(ResearchJob.player_id == pid)
            ).first()
            if rjob:
                pct, eta = self._progress(rjob.started_at, rjob.completes_at)
                self.has_research = True
                self.research_done_pct = pct
                self.research_eta = eta
                self.research_label = (
                    f"{g.RESEARCH[rjob.key].name} → {rjob.target_level}단계"
                )
            else:
                self.has_research = False

            my_nests = engine.nests_of(s, pid)
            self.nests_list = [
                [n.id or 0, n.name, n.x, n.y, n.is_main] for n in my_nests
            ]
            nest = self._nest(s)
            if nest is None:
                return
            self.nest_id = nest.id or 0

            rates = engine.process_nest(s, nest)
            sun_level = engine.get_building_level(s, nest.id, "sun_chamber")
            self.res_food = nest.res_food
            self.res_water = nest.res_water
            self.cap_food = rates["capacity"]
            self.prod_food = rates["food"]
            self.prod_water = rates["water"]
            self.energy = round(engine.sync_energy(s, player, sun_level), 1)
            self.points = round(engine.player_points(s, pid), 1)
            self.food_disp = f"{int(nest.res_food):,}"
            self.water_disp = f"{int(nest.res_water):,}"
            self.food_rate_disp = f"+{g.fmt_num(rates['food'])}/h"
            self.water_rate_disp = f"+{g.fmt_num(rates['water'])}/h"
            self.energy_disp = f"{self.energy:g}/{int(g.ENERGY_MAX)}"

            cjob = s.exec(
                select(ConstructionJob).where(ConstructionJob.nest_id == nest.id)
            ).first()
            if cjob:
                pct, eta = self._progress(cjob.started_at, cjob.completes_at)
                self.has_construction = True
                self.construction_done_pct = pct
                self.construction_eta = eta
                self.construction_label = (
                    f"{g.BUILDINGS[cjob.key].name} → {cjob.target_level}단계"
                )
            else:
                self.has_construction = False
            s.commit()

        if session is not None:
            _do_sync(session)
        else:
            with game_session() as s:
                _do_sync(s)

    @rx.event(background=True)
    async def refresh_game(self):
        async with self:
            if self._require_login():
                yield rx.redirect("/")
                return
            self._sync_game()

