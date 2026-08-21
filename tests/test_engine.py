"""Engine tests: resources, queues, marches, combat."""

from datetime import timedelta

from tests.conftest import make_army, make_nest, make_player, rewind, set_levels

from warant import engine, gamedata as g
from warant.models import (
    BroodJob,
    ConstructionJob,
    March,
    Report,
    ResearchJob,
    War,
)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


def test_resource_tick_accumulates(session):
    nest = make_nest(session, 1)
    rewind(nest)
    rates = engine.tick_nest(session, nest)
    session.commit()
    assert rates["food"] > 0
    assert nest.res_food > g.START_FOOD
    assert nest.res_food <= rates["capacity"]


def test_storage_cap_enforced(session):
    nest = make_nest(session, 1)
    set_levels(session, nest.id, {"granary": 2})
    nest.res_water = 50_000
    nest.last_tick_at = g.utc_now() - timedelta(hours=10_000)
    engine.tick_nest(session, nest)
    cap = g.storage_capacity(2)
    assert nest.res_water == cap


def test_energy_deficit_removed_from_production(session):
    """Production no longer depends on energy balance."""
    nest = make_nest(session, 1)
    levels = {"fungus_farm": 5}
    rates = engine.production_rates(session, nest, levels, {})
    assert rates["food"] > 0


def test_energy_regen_and_consume(session):
    from datetime import timedelta

    p = make_player(session, "energetic")
    p.energy = 50.0
    p.energy_updated_at = g.utc_now() - timedelta(hours=1)
    val = engine.sync_energy(session, p, sun_level=0)
    # base regen = 3600/300 = 12/hour
    assert abs(val - 62.0) < 0.5
    assert engine.consume_energy(session, p, 30.0) is True
    assert p.energy < 40.0
    p2 = make_player(session, "tired")
    p2.energy = 5.0
    p2.energy_updated_at = g.utc_now()
    assert engine.consume_energy(session, p2, 20.0) is False
    assert abs(p2.energy - 5.0) < 0.001


def test_sun_chamber_boosts_regen(session):
    rate0 = g.energy_regen_rate(0)
    rate5 = g.energy_regen_rate(5)
    assert rate5 == rate0 * 1.5


def test_research_boosts_production(session):
    nest = make_nest(session, 1)
    levels = {"fungus_farm": 3}
    base = engine.production_rates(session, nest, levels, {})["food"]
    boosted = engine.production_rates(session, nest, levels, {"foraging": 2})["food"]
    assert abs(boosted - base * 1.16) < 0.01


# ---------------------------------------------------------------------------
# Queues
# ---------------------------------------------------------------------------


def test_construction_completes(session):
    nest = make_nest(session, 1)
    job = ConstructionJob(
        nest_id=nest.id,
        key="granary",
        target_level=3,
        completes_at=g.utc_now() - timedelta(seconds=1),
    )
    session.add(job)
    engine.process_nest(session, nest)
    session.commit()
    assert engine.get_building_level(session, nest.id, "granary") == 3
    remaining = session.query(ConstructionJob).all()
    assert remaining == []


def test_construction_not_due_stays(session):
    nest = make_nest(session, 1)
    job = ConstructionJob(
        nest_id=nest.id,
        key="research_chamber",
        target_level=3,
        completes_at=g.utc_now() + timedelta(hours=1),
    )
    session.add(job)
    engine.process_nest(session, nest)
    session.commit()
    assert engine.get_building_level(session, nest.id, "research_chamber") == 0


def test_brood_delivers_incrementally(session):
    nest = make_nest(session, 1)
    unit_time = 60.0
    job = BroodJob(
        nest_id=nest.id,
        unit_key="worker",
        count=5,
        unit_seconds=unit_time,
        started_at=g.utc_now() - timedelta(seconds=int(unit_time * 2.5)),
    )
    session.add(job)
    engine.process_nest(session, nest)
    session.commit()
    army = engine.army_at(session, nest.id)
    assert army.get("worker") == 2  # 2 of 5 delivered so far
    jobs = session.query(BroodJob).all()
    assert len(jobs) == 1
    assert jobs[0].count == 3


def test_brood_batch_finishes_and_clears(session):
    nest = make_nest(session, 1)
    job = BroodJob(
        nest_id=nest.id,
        unit_key="soldier",
        count=2,
        unit_seconds=30.0,
        started_at=g.utc_now() - timedelta(seconds=120),
    )
    session.add(job)
    engine.process_nest(session, nest)
    session.commit()
    assert engine.army_at(session, nest.id).get("soldier") == 2
    assert session.query(BroodJob).all() == []


def test_research_completes(session):
    p = make_player(session)
    job = ResearchJob(
        player_id=p.id,
        key="foraging",
        target_level=1,
        completes_at=g.utc_now() - timedelta(seconds=5),
    )
    session.add(job)
    engine.process_player(session, p)
    session.commit()
    assert engine.research_levels(session, p.id).get("foraging") == 1


# ---------------------------------------------------------------------------
# Combat
# ---------------------------------------------------------------------------


def test_stronger_side_wins_battle():
    atk = {"major": 20}
    dfn = {"worker": 10}
    result = engine.battle_rounds(atk, dfn, 1.0, 1.0)
    assert result["winner"] == "attacker"
    assert sum(result["atk_survivors"].values()) > 0
    assert sum(result["def_survivors"].values()) == 0


def test_defense_with_thorn_bonus_can_hold():
    atk = {"soldier": 10}
    dfn = {"thorn_pit": 15}
    _, def_mult, _, _ = engine.combat_multipliers({}, {}, thorn_level=5, war_active=False)
    result = engine.battle_rounds(atk, dfn, 1.0, def_mult)
    assert result["winner"] == "defender"


def test_battle_rounds_are_limited():
    # Evenly matched huge stacks must end within COMBAT_MAX_ROUNDS rounds.
    atk = {"soldier": 500}
    dfn = {"soldier": 500}
    result = engine.battle_rounds(atk, dfn, 1.0, 1.0)
    assert len(result["rounds"]) <= g.COMBAT_MAX_ROUNDS


# ---------------------------------------------------------------------------
# Marches
# ---------------------------------------------------------------------------


def _mk_march(session, attacker, home, kind, tx, ty, units, **kw) -> March:
    m = March(
        player_id=attacker.id,
        from_nest_id=home.id,
        kind=kind,
        tx=tx,
        ty=ty,
        hx=home.x,
        hy=home.y,
        arrive_at=g.utc_now() - timedelta(seconds=1),
        **kw,
    )
    m.set_units(units)
    session.add(m)
    return m


def test_attack_win_loots_and_reports(session):
    attacker = make_player(session, "atk")
    defender = make_player(session, "def")
    home = make_nest(session, attacker.id, x=10, y=10)
    target = make_nest(session, defender.id, x=13, y=14, name="표적")
    make_army(session, target.id, {"pit_trap": 5})
    target.res_food = 2_000
    target.res_water = 1_000

    march = _mk_march(
        session, attacker, home, g.MARCH_ATTACK, target.x, target.y,
        {"soldier": 40}, target_nest_id=target.id,
    )
    handled = engine.process_due_marches(session)
    session.commit()

    assert handled >= 1
    # battle resolved into returning state
    assert march.status == "returning"
    assert march.return_at is not None
    # defender lost the traps
    assert engine.army_at(session, target.id).get("pit_trap", 0) < 5
    # reports for both sides
    reports = session.query(Report).all()
    assert {r.player_id for r in reports} == {attacker.id, defender.id}
    atk_rep = [r for r in reports if r.player_id == attacker.id][0]
    assert atk_rep.body()["role"] == "attacker"


def test_attack_loss_no_loot(session):
    attacker = make_player(session, "weak")
    defender = make_player(session, "strong")
    home = make_nest(session, attacker.id, x=10, y=10)
    target = make_nest(session, defender.id, x=12, y=12, name="요새")
    make_army(session, target.id, {"acid_sprayer": 20})
    before_f, before_w = target.res_food, target.res_water

    march = _mk_march(
        session, attacker, home, g.MARCH_ATTACK, target.x, target.y,
        {"worker": 5}, target_nest_id=target.id,
    )
    engine.process_due_marches(session)
    session.commit()

    body = [
        r.body() for r in session.query(Report).all() if r.player_id == attacker.id
    ][0]
    assert body["winner"] == "defender"
    assert body["loot_food"] == 0 and body["loot_water"] == 0
    assert (target.res_food, target.res_water) == (before_f, before_w)
    # 5 workers vs 20 acid sprayers = total wipe
    assert sum(march.units().values()) == 0
    assert march.status == "returning"


def test_scout_success_and_caught(session):
    attacker = make_player(session, "spy")
    defender = make_player(session, "victim")
    home = make_nest(session, attacker.id)
    target = make_nest(session, defender.id, x=55, y=52, name="둥지")

    m1 = _mk_march(
        session, attacker, home, g.MARCH_SCOUT, target.x, target.y,
        {"scout": 10}, target_nest_id=target.id,
    )
    engine.process_due_marches(session)
    session.commit()
    rep = [
        r.body() for r in session.query(Report).all() if r.kind == "scout"
    and r.player_id == attacker.id
    ][0]
    assert rep["success"] is True
    assert "res_food" in rep
    assert m1.status == "returning"

    # now scout against heavy watch post -> caught
    set_levels(session, target.id, {"watch_post": 8})
    m2 = _mk_march(
        session, attacker, home, g.MARCH_SCOUT, target.x, target.y,
        {"scout": 2}, target_nest_id=target.id,
    )
    engine.process_due_marches(session)
    session.commit()
    bodies = sorted(
        [r.body() for r in session.query(Report).all()],
        key=lambda b: str(b),
    )
    caught_reports = [b for b in bodies if b.get("success") is False]
    assert caught_reports, "expected at least one failed scout report"
    assert m2.status == "done"  # all scouts destroyed


def test_hunt_yields_resources(session):
    p = make_player(session, "hunter")
    home = make_nest(session, p.id)
    march = _mk_march(
        session, p, home, g.MARCH_HUNT, 70, 70, {"soldier": 40}
    )
    engine.process_due_marches(session)
    session.commit()
    assert march.status in ("returning", "done")
    rep = [r.body() for r in session.query(Report).all() if r.kind == "hunt"][0]
    assert "coord" in rep
    # soldiers should survive a wild stack and bring food home
    if march.status == "returning":
        assert march.cargo_food + march.cargo_water > 0


def test_transfer_moves_resources_between_own_nests(session):
    p = make_player(session, "mover")
    home = make_nest(session, p.id, x=20, y=20, name="본가")
    other = make_nest(session, p.id, x=23, y=24, name="분가")

    march = _mk_march(
        session, p, home, g.MARCH_TRANSFER, other.x, other.y,
        {"worker": 5},
        target_nest_id=other.id, cargo_food=500.0, cargo_water=250.0,
    )
    engine.process_due_marches(session)
    session.commit()

    # tick clamps stores to granary L1 capacity, then the cargo is added
    expected = min(10_000, g.storage_capacity(1)) + 500
    assert other.res_food == expected
    assert march.cargo_food == 0.0
    assert march.status == "returning"

    # homecoming delivers the carriers back
    march.return_at = g.utc_now() - timedelta(seconds=1)
    engine.process_due_marches(session)
    session.commit()
    assert march.status == "done"
    assert engine.army_at(session, home.id).get("worker") == 5


def test_deploy_leaves_units_at_target(session):
    p = make_player(session, "reloc")
    home = make_nest(session, p.id, x=40, y=40)
    other = make_nest(session, p.id, x=44, y=41, name="전초기지")
    march = _mk_march(
        session, p, home, g.MARCH_DEPLOY, other.x, other.y,
        {"soldier": 12}, target_nest_id=other.id,
    )
    engine.process_due_marches(session)
    session.commit()
    assert march.status == "done"
    assert engine.army_at(session, other.id).get("soldier") == 12


def test_war_score_accumulates(session):
    from warant.models import Alliance

    a1 = Alliance(name="붉은군체", tag="RED", leader_id=1)
    a2 = Alliance(name="검은굴", tag="BLK", leader_id=2)
    session.add(a1)
    session.add(a2)
    session.flush()
    attacker = make_player(session, "waratk")
    attacker.alliance_id = a1.id
    defender = make_player(session, "wardef")
    defender.alliance_id = a2.id
    war = War(
        alliance_a_id=a1.id, alliance_b_id=a2.id,
        ends_at=g.utc_now() + timedelta(days=3), active=True,
    )
    session.add(war)

    home = make_nest(session, attacker.id, x=5, y=5)
    target = make_nest(session, defender.id, x=7, y=6, name="적영")
    make_army(session, target.id, {"thorn_pit": 30})

    _mk_march(
        session, attacker, home, g.MARCH_ATTACK, target.x, target.y,
        {"major": 50}, target_nest_id=target.id,
    )
    engine.process_due_marches(session)
    session.commit()
    session.refresh(war)
    total_score = war.score_a + war.score_b
    assert total_score > 0


# ---------------------------------------------------------------------------
# Creation helpers
# ---------------------------------------------------------------------------


def test_create_starting_nest(session):
    p = make_player(session, "queen")
    x, y = engine.find_free_coord(session)
    nest = engine.create_starting_nest(session, p, x, y, "모종")
    session.commit()
    assert engine.get_building_level(session, nest.id, "brood_chamber") == 1
    assert engine.army_at(session, nest.id)["worker"] == 8


def test_newbie_protection(session):
    young = make_player(session, "youngling")
    assert engine.is_protected(session, young)
    old = make_player(session, "elder")
    old.created_at = g.utc_now() - timedelta(days=30)
    small_nest = make_nest(session, old.id)
    set_levels(session, small_nest.id, {})
    # elder has tiny points -> still protected by points rule
    assert engine.is_protected(session, old)
