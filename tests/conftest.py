"""Shared test fixtures: in-memory database and player factories."""

from datetime import timedelta

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from warant import gamedata as g
from warant.models import Army, BuildingLevel, Nest, Player


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def make_player(session: Session, username: str = "tester") -> Player:
    p = Player(username=username, password_hash="x")
    session.add(p)
    session.flush()
    return p


def make_nest(
    session: Session, player_id: int, x: int = 50, y: int = 50, name: str = "본가"
) -> Nest:
    nest = Nest(
        player_id=player_id,
        name=name,
        x=x,
        y=y,
        is_main=True,
        res_food=10_000,
        res_water=10_000,
        last_tick_at=g.utc_now(),
    )
    session.add(nest)
    session.flush()
    for key in ("fungus_farm", "dew_collector", "sun_chamber", "granary"):
        session.add(BuildingLevel(nest_id=nest.id, key=key, level=1))
    return nest


def set_levels(session: Session, nest_id: int, levels: dict[str, int]) -> None:
    for key, lvl in levels.items():
        session.add(BuildingLevel(nest_id=nest_id, key=key, level=lvl))


def make_army(session: Session, nest_id: int, units: dict[str, int]) -> None:
    for key, cnt in units.items():
        session.add(Army(nest_id=nest_id, unit_key=key, count=cnt))


def rewind(nest: Nest, hours: float = 1.0) -> None:
    nest.last_tick_at = g.utc_now() - timedelta(hours=hours)
