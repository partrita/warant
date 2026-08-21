"""WarAnt database models (SQLModel)."""

from __future__ import annotations

import json
from datetime import datetime

from sqlmodel import Field, SQLModel

from . import gamedata as g


def now() -> datetime:
    return g.utc_now()


class Player(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    created_at: datetime = Field(default_factory=now)
    alliance_id: int | None = Field(default=None, index=True)
    # Action energy (max 100, refills over time)
    energy: float = g.ENERGY_MAX
    energy_updated_at: datetime = Field(default_factory=now)


class Nest(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    player_id: int = Field(index=True, foreign_key="player.id")
    name: str
    x: int = Field(index=True)
    y: int = Field(index=True)
    is_main: bool = False
    res_food: float = g.START_FOOD
    res_water: float = g.START_WATER
    last_tick_at: datetime = Field(default_factory=now)

    @property
    def coord(self) -> str:
        return f"{self.x}:{self.y}"


class BuildingLevel(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nest_id: int = Field(index=True, foreign_key="nest.id")
    key: str = Field(index=True)
    level: int = 0


class ConstructionJob(SQLModel, table=True):
    """One building upgrade in progress per nest."""

    id: int | None = Field(default=None, primary_key=True)
    nest_id: int = Field(index=True, foreign_key="nest.id")
    key: str
    target_level: int
    started_at: datetime = Field(default_factory=now)
    completes_at: datetime = Field(index=True)


class ResearchLevel(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    player_id: int = Field(index=True, foreign_key="player.id")
    key: str = Field(index=True)
    level: int = 0


class ResearchJob(SQLModel, table=True):
    """One research in progress per player."""

    id: int | None = Field(default=None, primary_key=True)
    player_id: int = Field(index=True, foreign_key="player.id")
    nest_id: int = Field(default=0)  # chamber used
    key: str
    target_level: int
    started_at: datetime = Field(default_factory=now)
    completes_at: datetime = Field(index=True)


class BroodJob(SQLModel, table=True):
    """A batch of identical units being brooded; delivered incrementally."""

    id: int | None = Field(default=None, primary_key=True)
    nest_id: int = Field(index=True, foreign_key="nest.id")
    unit_key: str
    count: int
    unit_seconds: float  # build time per unit at job start
    started_at: datetime


class Army(SQLModel, table=True):
    """Units stationed at a nest (mobile army + stationary defenses)."""

    id: int | None = Field(default=None, primary_key=True)
    nest_id: int = Field(index=True, foreign_key="nest.id")
    unit_key: str = Field(index=True)
    count: int = 0


class March(SQLModel, table=True):
    """Units moving on the map. Lifecycle: outbound -> returning -> done."""

    id: int | None = Field(default=None, primary_key=True)
    player_id: int = Field(index=True, foreign_key="player.id")
    from_nest_id: int = Field(foreign_key="nest.id")
    kind: str  # MARCH_*
    tx: int  # target coordinate
    ty: int
    hx: int = 0  # home coordinate (origin nest)
    hy: int = 0
    target_nest_id: int | None = None
    units_json: str = "{}"  # {"worker": 10, ...}
    cargo_food: float = 0.0  # for transfer marches
    cargo_water: float = 0.0
    depart_at: datetime = Field(default_factory=now)
    arrive_at: datetime = Field(index=True)
    hold_until: datetime | None = None  # hunt/scout linger end
    return_at: datetime | None = Field(default=None, index=True)
    status: str = "outbound"  # outbound | holding | returning | done
    payload_json: str = "{}"  # resolution results for reports

    def units(self) -> dict[str, int]:
        return json.loads(self.units_json or "{}")

    def set_units(self, u: dict[str, int]) -> None:
        self.units_json = json.dumps(u)

    def payload(self) -> dict:
        return json.loads(self.payload_json or "{}")

    def set_payload(self, p: dict) -> None:
        self.payload_json = json.dumps(p, ensure_ascii=False)


REPORT_BATTLE = "battle"
REPORT_SCOUT = "scout"
REPORT_HUNT = "hunt"
REPORT_TRANSFER = "transfer"
REPORT_DEPLOY = "deploy"
REPORT_INCOMING = "incoming"
REPORT_SYSTEM = "system"


class Report(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    player_id: int = Field(index=True, foreign_key="player.id")
    kind: str
    title: str
    body_json: str = "{}"
    created_at: datetime = Field(default_factory=now, index=True)
    is_read: bool = False

    def body(self) -> dict:
        return json.loads(self.body_json or "{}")

    def set_body(self, b: dict) -> None:
        self.body_json = json.dumps(b, ensure_ascii=False)


class Alliance(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    tag: str = Field(unique=True)
    leader_id: int = Field(foreign_key="player.id")
    description: str = ""
    created_at: datetime = Field(default_factory=now)


class War(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    alliance_a_id: int = Field(index=True, foreign_key="alliance.id")
    alliance_b_id: int = Field(index=True, foreign_key="alliance.id")
    score_a: float = 0.0
    score_b: float = 0.0
    declared_at: datetime = Field(default_factory=now)
    ends_at: datetime = Field(index=True)
    active: bool = True
