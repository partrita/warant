"""Tests for colony ant population limits."""

from tests.conftest import make_nest
from warant import gamedata as g
from warant.models import BroodJob
from warant.pages.brood import (
    queued_mobile_ants,
)


def test_ant_population_cap_grows_with_housing():
    assert g.ant_population_cap(0) == g.BASE_ANT_CAP
    assert g.ant_population_cap(1) == g.BASE_ANT_CAP + g.ANT_CAP_PER_HOUSING
    assert g.ant_population_cap(4) == g.BASE_ANT_CAP + 4 * g.ANT_CAP_PER_HOUSING


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
