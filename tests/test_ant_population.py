"""Tests for colony ant population limits."""

from warant.pages.brood import (
    ANT_CAP_PER_METABOLISM,
    BASE_ANT_CAP,
    ant_population_cap,
    queued_mobile_ants,
)
from warant.models import BroodJob
from tests.conftest import make_nest
from warant import gamedata as g


def test_ant_population_cap_grows_with_metabolism():
    assert ant_population_cap({}) == BASE_ANT_CAP
    assert ant_population_cap({"metabolism": 1}) == BASE_ANT_CAP + ANT_CAP_PER_METABOLISM
    assert ant_population_cap({"metabolism": 4}) == 150


def test_queued_mobile_ants_excludes_defenses(session):
    nest = make_nest(session, 1)
    session.add(
        BroodJob(
            nest_id=nest.id,
            unit_key="worker",
            count=12,
            unit_seconds=10,
            started_at=g.utc_now(),
        )
    )
    session.add(
        BroodJob(
            nest_id=nest.id,
            unit_key="pit_trap",
            count=8,
            unit_seconds=10,
            started_at=g.utc_now(),
        )
    )
    session.commit()
    assert queued_mobile_ants(session, nest.id) == 12
