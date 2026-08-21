"""WarAnt game engine: resource ticking, queues, marches, and combat.

The engine is *lazy* (OGame-style): every read/write funnels through
`process_player`, which fast-forwards the nest to the current time by
resolving completed jobs, brood deliveries, resource production, and
due marches. A background ticker calls `process_all` periodically so
marches resolve even when nobody is watching.
"""

from __future__ import annotations

import math
import random
from datetime import timedelta

from sqlmodel import select

from . import gamedata as g
from .models import (
    Army,
    BroodJob,
    BuildingLevel,
    ConstructionJob,
    March,
    Nest,
    Player,
    Report,
    ResearchJob,
    ResearchLevel,
    War,
)

RNG = random.Random()


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------


def building_levels(session, nest_id: int) -> dict[str, int]:
    rows = session.exec(
        select(BuildingLevel).where(BuildingLevel.nest_id == nest_id)
    ).all()
    return {r.key: r.level for r in rows}


def get_building_level(session, nest_id: int, key: str) -> int:
    row = session.exec(
        select(BuildingLevel).where(
            BuildingLevel.nest_id == nest_id, BuildingLevel.key == key
        )
    ).first()
    return row.level if row else 0


def research_levels(session, player_id: int) -> dict[str, int]:
    rows = session.exec(
        select(ResearchLevel).where(ResearchLevel.player_id == player_id)
    ).all()
    return {r.key: r.level for r in rows}


def army_at(session, nest_id: int) -> dict[str, int]:
    rows = session.exec(select(Army).where(Army.nest_id == nest_id)).all()
    return {r.unit_key: r.count for r in rows if r.count > 0}


def add_army(session, nest_id: int, units: dict[str, int]) -> None:
    """Add units to a nest's garrison."""
    for key, count in units.items():
        if count <= 0:
            continue
        row = session.exec(
            select(Army).where(Army.nest_id == nest_id, Army.unit_key == key)
        ).first()
        if row:
            row.count += count
        else:
            session.add(Army(nest_id=nest_id, unit_key=key, count=count))


def remove_army(session, nest_id: int, units: dict[str, int]) -> bool:
    """Remove units from a nest's garrison. Returns False if insufficient."""
    have = army_at(session, nest_id)
    for key, count in units.items():
        if count > 0 and have.get(key, 0) < count:
            return False
    for key, count in units.items():
        if count <= 0:
            continue
        row = session.exec(
            select(Army).where(Army.nest_id == nest_id, Army.unit_key == key)
        ).first()
        row.count -= count
    return True


def nests_of(session, player_id: int) -> list[Nest]:
    return session.exec(
        select(Nest).where(Nest.player_id == player_id).order_by(Nest.is_main.desc(), Nest.id)
    ).all()


def get_nest(session, nest_id: int) -> Nest | None:
    return session.get(Nest, nest_id)


def player_points(session, player_id: int) -> float:
    total = 0.0
    for nest in nests_of(session, player_id):
        for key, lvl in building_levels(session, nest.id).items():
            total += g.building_points(key, lvl)
        for key, cnt in army_at(session, nest.id).items():
            total += g.unit_points(key) * cnt
    for key, lvl in research_levels(session, player_id).items():
        total += g.research_points(key, lvl)
    return total


def is_protected(session, target_player: Player) -> bool:
    """Newbie protection: fresh or small colonies cannot be attacked."""
    age_h = (g.utc_now() - target_player.created_at).total_seconds() / 3_600
    if age_h < g.NEWBIE_PROTECTION_HOURS:
        return True
    return player_points(session, target_player.id) < g.NEWBIE_PROTECTION_POINTS


def war_between(session, alliance_a: int | None, alliance_b: int | None) -> War | None:
    """Active war between two alliances, if any."""
    if not alliance_a or not alliance_b or alliance_a == alliance_b:
        return None
    wars = session.exec(select(War).where(War.active == True)).all()  # noqa: E712
    for w in wars:
        if {w.alliance_a_id, w.alliance_b_id} == {alliance_a, alliance_b}:
            if w.ends_at > g.utc_now():
                return w
            w.active = False
            session.add(w)
    return None


# ---------------------------------------------------------------------------
# Resource ticking
# ---------------------------------------------------------------------------


def production_rates(session, nest: Nest, levels: dict[str, int], research: dict[str, int]) -> dict:
    food = water = 0.0
    for key, lvl in levels.items():
        f, w = g.building_prod(key, lvl)
        food += f
        water += w
    food *= 1.0 + 0.08 * research.get("foraging", 0)
    water *= 1.0 + 0.08 * research.get("hydration", 0)
    cap = g.storage_capacity(levels.get("granary", 0))
    return {
        "food": food,
        "water": water,
        "capacity": cap,
    }


def current_energy(player: Player, sun_level: int = 0) -> float:
    """Lazy energy refill: stored + elapsed * regen rate, capped at max."""
    if player.energy >= g.ENERGY_MAX:
        player.energy_updated_at = g.utc_now()
        return g.ENERGY_MAX
    hours = (g.utc_now() - player.energy_updated_at).total_seconds() / 3_600
    gained = hours * g.energy_regen_rate(sun_level)
    return min(g.ENERGY_MAX, player.energy + gained)


def sync_energy(session, player: Player, sun_level: int = 0) -> float:
    """Persist lazy energy refill and return the new value."""
    val = current_energy(player, sun_level)
    player.energy = val
    player.energy_updated_at = g.utc_now()
    session.add(player)
    return val


def consume_energy(session, player: Player, amount: float, sun_level: int = 0) -> bool:
    """Try to spend action energy. Returns False (and spends nothing) if short."""
    have = sync_energy(session, player, sun_level)
    if have < amount:
        return False
    player.energy = have - amount
    player.energy_updated_at = g.utc_now()
    session.add(player)
    return True


def tick_nest(session, nest: Nest, research: dict[str, int] | None = None) -> dict:
    """Fast-forward one nest's resources to now. Returns rates snapshot."""
    t_now = g.utc_now()
    levels = building_levels(session, nest.id)
    research = research or {}
    rates = production_rates(session, nest, levels, research)
    dt_h = (t_now - nest.last_tick_at).total_seconds() / 3_600
    if dt_h > 0:
        nest.res_food = min(rates["capacity"], nest.res_food + rates["food"] * dt_h)
        nest.res_water = min(rates["capacity"], nest.res_water + rates["water"] * dt_h)
        nest.last_tick_at = t_now
        session.add(nest)
    return rates


# ---------------------------------------------------------------------------
# Queue completion
# ---------------------------------------------------------------------------


def _complete_constructions(session, nest: Nest) -> None:
    t_now = g.utc_now()
    jobs = session.exec(
        select(ConstructionJob).where(
            ConstructionJob.nest_id == nest.id, ConstructionJob.completes_at <= t_now
        )
    ).all()
    for job in jobs:
        row = session.exec(
            select(BuildingLevel).where(
                BuildingLevel.nest_id == nest.id, BuildingLevel.key == job.key
            )
        ).first()
        if row:
            row.level = job.target_level
        else:
            session.add(
                BuildingLevel(nest_id=nest.id, key=job.key, level=job.target_level)
            )
        session.delete(job)


def _complete_research(session, player_id: int) -> None:
    t_now = g.utc_now()
    jobs = session.exec(
        select(ResearchJob).where(
            ResearchJob.player_id == player_id, ResearchJob.completes_at <= t_now
        )
    ).all()
    for job in jobs:
        row = session.exec(
            select(ResearchLevel).where(
                ResearchLevel.player_id == player_id, ResearchLevel.key == job.key
            )
        ).first()
        if row:
            row.level = job.target_level
        else:
            session.add(
                ResearchLevel(player_id=player_id, key=job.key, level=job.target_level)
            )
        session.delete(job)


def _deliver_brood(session, nest: Nest) -> None:
    t_now = g.utc_now()
    jobs = session.exec(select(BroodJob).where(BroodJob.nest_id == nest.id)).all()
    for job in jobs:
        elapsed = (t_now - job.started_at).total_seconds()
        done = min(job.count, int(elapsed // max(job.unit_seconds, 0.001)))
        if done <= 0:
            continue
        add_army(session, nest.id, {job.unit_key: done})
        remaining = job.count - done
        if remaining > 0:
            job.count = remaining
            job.started_at = job.started_at + timedelta(seconds=done * job.unit_seconds)
            session.add(job)
        else:
            session.delete(job)


def process_nest(session, nest: Nest, research: dict[str, int] | None = None) -> dict:
    """Complete due jobs and tick resources for one nest."""
    _complete_constructions(session, nest)
    _deliver_brood(session, nest)
    return tick_nest(session, nest, research)


def process_player(session, player: Player) -> None:
    """Full lazy update for a player: research, all nests, own marches."""
    _complete_research(session, player.id)
    research = research_levels(session, player.id)
    for nest in nests_of(session, player.id):
        process_nest(session, nest, research)


# ---------------------------------------------------------------------------
# Combat
# ---------------------------------------------------------------------------


def unit_def(key: str):
    return g.UNITS.get(key) or g.WILD_INSECTS.get(key)


def _split_losses(units: dict[str, int], damage_frac: float) -> dict[str, int]:
    """Kill a fraction of each stack (equal fraction across unit types)."""
    losses = {}
    frac = min(1.0, max(0.0, damage_frac))
    for key, cnt in units.items():
        killed = math.floor(cnt * frac + RNG.random())
        losses[key] = min(cnt, killed)
    return losses


def battle_rounds(
    atk_units: dict[str, int],
    def_units: dict[str, int],
    atk_mult: float,
    def_mult: float,
    atk_chitin: float = 1.0,
    def_chitin: float = 1.0,
) -> dict:
    """Simulate up to COMBAT_MAX_ROUNDS rounds; returns full battle record."""

    def hull_pool(units: dict[str, int], chitin: float) -> float:
        return sum(unit_def(k).hull * c for k, c in units.items()) * chitin

    def power(units: dict[str, int], stat: str, mult: float) -> float:
        return sum(getattr(unit_def(k), stat) * c for k, c in units.items()) * mult

    atk = dict(atk_units)
    dfn = dict(def_units)
    rounds_log = []
    winner = None
    for rnd in range(1, g.COMBAT_MAX_ROUNDS + 1):
        if not any(c > 0 for c in atk.values()):
            winner = "defender"
            break
        if not any(c > 0 for c in dfn.values()):
            winner = "attacker"
            break
        a_pow = power(atk, "attack", atk_mult) * (1 + RNG.uniform(-g.COMBAT_VARIANCE, g.COMBAT_VARIANCE))
        d_pow = power(dfn, "defense", def_mult) * (1 + RNG.uniform(-g.COMBAT_VARIANCE, g.COMBAT_VARIANCE))
        a_hull = hull_pool(atk, atk_chitin)
        d_hull = hull_pool(dfn, def_chitin)
        rounds_log.append(
            {
                "round": rnd,
                "atk_power": round(a_pow),
                "def_power": round(d_pow),
                "atk_hull": round(a_hull),
                "def_hull": round(d_hull),
            }
        )
        a_loss_frac = d_pow / a_hull if a_hull > 0 else 1.0
        d_loss_frac = a_pow / d_hull if d_hull > 0 else 1.0
        a_losses = _split_losses(atk, a_loss_frac)
        d_losses = _split_losses(dfn, d_loss_frac)
        for k, v in a_losses.items():
            atk[k] -= v
        for k, v in d_losses.items():
            dfn[k] -= v
    if winner is None:
        # After N rounds: side with higher surviving strength fraction wins.
        a_alive = sum(atk.values())
        d_alive = sum(dfn.values())
        winner = "attacker" if a_alive >= d_alive else "defender"
    return {
        "rounds": rounds_log,
        "winner": winner,
        "atk_survivors": {k: v for k, v in atk.items() if v > 0},
        "def_survivors": {k: v for k, v in dfn.items() if v > 0},
    }


def combat_multipliers(
    atk_research: dict[str, int],
    def_research: dict[str, int],
    thorn_level: int,
    war_active: bool,
) -> tuple[float, float, float, float]:
    """(atk_mult, def_mult, atk_chitin, def_chitin)."""
    atk_mult = (
        (1 + 0.08 * atk_research.get("mandibles", 0))
        * (1 + 0.06 * atk_research.get("swarm_tactics", 0))
        * (1.25 if war_active else 1.0)
    )
    def_mult = (1 + 0.08 * def_research.get("chitin", 0)) * (
        1 + g.THORN_GATE_DEF_BONUS * thorn_level
    )
    chitin_a = 1 + 0.08 * atk_research.get("chitin", 0)
    chitin_d = 1 + 0.08 * def_research.get("chitin", 0)
    return atk_mult, def_mult, chitin_a, chitin_d


# ---------------------------------------------------------------------------
# March resolution
# ---------------------------------------------------------------------------


def _slowest_speed(units: dict[str, int]) -> int:
    speeds = [g.UNITS[k].speed for k, c in units.items() if c > 0]
    return min(speeds) if speeds else 6


def _travel_time_back(march: March, tunneling: int) -> float:
    dist = coord_distance(march.tx, march.ty, march.hx, march.hy)
    return g.travel_seconds(dist, _slowest_speed(march.units()), tunneling)


def coord_distance(x1: int, y1: int, x2: int, y2: int) -> float:
    return math.hypot(x2 - x1, y2 - y1)


def _add_report(session, player_id: int, kind: str, title: str, body: dict) -> None:
    rep = Report(player_id=player_id, kind=kind, title=title)
    rep.set_body(body)
    session.add(rep)


def _loot_capacity(units: dict[str, int]) -> float:
    return sum(g.UNITS[k].cargo * c for k, c in units.items())


def _resolve_attack(session, march: March) -> None:
    attacker = session.get(Player, march.player_id)
    target = session.get(Nest, march.target_nest_id)
    if target is None:
        march.status = "done"
        return
    defender = session.get(Player, target.player_id)

    atk_units = march.units()
    def_before = army_at(session, target.id)
    atk_res = research_levels(session, attacker.id)
    def_res = research_levels(session, defender.id)
    thorn = get_building_level(session, target.id, "thorn_gate")

    war = war_between(session, attacker.alliance_id, defender.alliance_id)
    atk_mult, def_mult, chin_a, chin_d = combat_multipliers(
        atk_res, def_res, thorn, war is not None
    )

    result = battle_rounds(atk_units, def_before, atk_mult, def_mult, chin_a, chin_d)
    survivors = result["atk_survivors"]
    def_after = result["def_survivors"]

    # Apply defender losses to the garrison.
    for key, before in def_before.items():
        lost = before - def_after.get(key, 0)
        if lost > 0:
            remove_army(session, target.id, {key: lost})

    # Loot on attacker victory.
    loot_f = loot_w = 0.0
    if result["winner"] == "attacker":
        tick_nest(session, target, def_res)
        cap = _loot_capacity(survivors) * g.LOOT_EFFICIENCY
        hidden = g.hidden_resources(get_building_level(session, target.id, "tunnel_network"))
        avail_f = max(0.0, target.res_food - hidden)
        avail_w = max(0.0, target.res_water - hidden)
        loot_f = min(avail_f, cap / 2)
        loot_w = min(avail_w, cap / 2)
        target.res_food -= loot_f
        target.res_water -= loot_w
        session.add(target)

    # War score from losses value on both sides.
    if war is not None:
        def_loss_value = sum(
            (before - def_after.get(k, 0)) * (g.UNITS[k].food + g.UNITS[k].water)
            for k, before in def_before.items()
        )
        atk_loss_value = sum(
            (c - survivors.get(k, 0)) * (g.UNITS[k].food + g.UNITS[k].water)
            for k, c in atk_units.items()
        )
        attacker_score = def_loss_value / g.KILL_POINT_DIVISOR
        defender_score = atk_loss_value / g.KILL_POINT_DIVISOR
        if attacker.alliance_id == war.alliance_a_id:
            war.score_a += attacker_score
            war.score_b += defender_score
        else:
            war.score_b += attacker_score
            war.score_a += defender_score
        session.add(war)

    battle_record = {
        "winner": result["winner"],
        "rounds": result["rounds"],
        "atk_sent": atk_units,
        "atk_losses": {k: c - survivors.get(k, 0) for k, c in atk_units.items()},
        "def_losses": {
            k: before - def_after.get(k, 0) for k, before in def_before.items()
        },
        "def_survivors": def_after,
        "loot_food": round(loot_f),
        "loot_water": round(loot_w),
        "war": war is not None,
        "coord": f"{target.x}:{target.y}",
        "target_owner": defender.username,
        "attacker_name": attacker.username,
    }

    march.set_units(survivors)
    march.cargo_food = loot_f
    march.cargo_water = loot_w
    back = _travel_time_back(march, atk_res.get("tunneling", 0))
    now = g.utc_now()
    march.status = "returning"
    march.arrive_at = now
    march.return_at = now + timedelta(seconds=back)

    _add_report(
        session,
        attacker.id,
        "battle",
        f"{g.fmt_coord(target.x, target.y)} 공격 결과 — "
        + ("승리" if result["winner"] == "attacker" else "패배"),
        {**battle_record, "role": "attacker"},
    )
    _add_report(
        session,
        defender.id,
        "battle",
        f"{attacker.username}의 공격 ({g.fmt_coord(target.x, target.y)}) — "
        + ("방어 성공" if result["winner"] == "defender" else "수비 실패"),
        {**battle_record, "role": "defender"},
    )


def _resolve_scout(session, march: March) -> None:
    attacker = session.get(Player, march.player_id)
    target = session.get(Nest, march.target_nest_id)
    if target is None:
        march.status = "done"
        return
    defender = session.get(Player, target.player_id)

    scouts = march.units().get("scout", 0)
    atk_res = research_levels(session, attacker.id)
    scent = atk_res.get("scent_tracking", 0)
    watch = get_building_level(session, target.id, "watch_post")
    def_scouts = army_at(session, target.id).get("scout", 0)

    atk_stealth = scouts * (12 + 4 * scent)
    counter = def_scouts * (10 + 3 * watch) + watch * 25

    caught = 0
    success = True
    detail = {}
    if counter >= atk_stealth:
        success = False
        caught = scouts  # detected: scouts destroyed
        body = {"success": False, "caught": caught}
    elif counter >= atk_stealth * 0.5:
        caught = math.floor(scouts * 0.3)
        body = {"success": True, "partial": True}
    else:
        body = {"success": True}

    if success:
        tick_nest(session, target)
        levels = building_levels(session, target.id)
        detail = {
            "res_food": round(target.res_food),
            "res_water": round(target.res_water),
            "buildings": {k: v for k, v in levels.items() if v > 0},
            "army": army_at(session, target.id),
            "owner": defender.username,
            "coord": f"{target.x}:{target.y}",
            "partial": body.get("partial", False),
        }
        body.update(detail)
        if body.get("partial"):
            # fuzz exact numbers on partial success
            body["res_food"] = round(body["res_food"] * RNG.uniform(0.7, 1.3), -2)
            body["res_water"] = round(body["res_water"] * RNG.uniform(0.7, 1.3), -2)
    _add_report(
        session,
        attacker.id,
        "scout",
        f"{g.fmt_coord(target.x, target.y)} 정찰 보고",
        body,
    )
    _add_report(
        session,
        defender.id,
        "scout",
        f"{attacker.username}의 정찰개미를 감지했습니다 ({g.fmt_coord(target.x, target.y)})",
        {"success": success, "by": attacker.username},
    )

    units = march.units()
    if caught:
        remaining = max(0, units.get("scout", 0) - caught)
        units["scout"] = remaining
        march.set_units(units)
    if sum(units.values()) <= 0:
        march.status = "done"
        return
    back = _travel_time_back(march, atk_res.get("tunneling", 0))
    now = g.utc_now()
    march.status = "returning"
    march.arrive_at = now
    march.hold_until = None
    march.return_at = now + timedelta(seconds=g.SCOUT_HOLD_S + back)


WILD_ENCOUNTER_KEYS = ["beetle", "spider", "wasp", "mantis"]


def _wild_stack(distance_from_center: float, rng: random.Random) -> dict[str, int]:
    """Wild insects scale with how deep into the wilderness you hunt."""
    depth = min(1.0, distance_from_center / 70.0)
    tier = rng.random() < 0.15 + 0.35 * depth  # chance of dangerous insects
    pool = WILD_ENCOUNTER_KEYS[2:] if tier else WILD_ENCOUNTER_KEYS[:2]
    key = rng.choice(pool)
    size = rng.randint(4, 14) + int(depth * rng.randint(5, 20))
    return {key: size}


def _resolve_hunt(session, march: March) -> None:
    player = session.get(Player, march.player_id)
    res = research_levels(session, player.id)
    rng = random.Random(march.id * 7919)
    center = g.MAP_SIZE / 2
    dist_center = math.hypot(march.tx - center, march.ty - center)

    units = march.units()
    wild = _wild_stack(dist_center, rng)
    atk_mult = (1 + 0.08 * res.get("mandibles", 0)) * (1 + 0.06 * res.get("swarm_tactics", 0))
    result = battle_rounds(units, wild, atk_mult, 1.0 + 0.05 * dist_center / 50)

    survivors = result["atk_survivors"]
    # Gather yield based on surviving cargo and hunt duration.
    cap = _loot_capacity(survivors) * g.LOOT_EFFICIENCY
    base_yield = 900 + 26 * dist_center  # deeper wilderness = richer pickings
    gathered_total = min(cap, base_yield)
    share = rng.uniform(0.45, 0.65)
    food = round(gathered_total * share)
    water = round(gathered_total * (1 - share))

    losses = {k: c - survivors.get(k, 0) for k, c in units.items()}
    march.set_units(survivors)
    march.cargo_food = food
    march.cargo_water = water
    march.set_payload(
        {
            **march.payload(),
            "hunt": {
                "wild": wild,
                "wild_losses": {k: c - result["def_survivors"].get(k, 0) for k, c in wild.items()},
                "losses": {k: v for k, v in losses.items() if v > 0},
                "food": food,
                "water": water,
                "coord": f"{march.tx}:{march.ty}",
            },
        }
    )
    if sum(survivors.values()) <= 0:
        _add_report(
            session,
            player.id,
            "hunt",
            f"사냥 실패 ({march.tx}:{march.ty})",
            {**march.payload()["hunt"], "wiped": True},
        )
        march.status = "done"
        return
    _add_report(
        session,
        player.id,
        "hunt",
        f"사냥 결과 ({march.tx}:{march.ty})",
        march.payload()["hunt"],
    )
    back = _travel_time_back(march, res.get("tunneling", 0))
    now = g.utc_now()
    march.status = "returning"
    march.arrive_at = now
    march.return_at = now + timedelta(seconds=back)


def _resolve_transfer(session, march: March) -> None:
    target = session.get(Nest, march.target_nest_id)
    if target is None or target.player_id != march.player_id:
        march.status = "done"
        return
    tick_nest(session, target)
    target.res_food += march.cargo_food
    target.res_water += march.cargo_water
    session.add(target)
    _add_report(
        session,
        march.player_id,
        "transfer",
        f"이송 완료 → {target.name} ({target.coord})",
        {
            "to": target.name,
            "coord": target.coord,
            "food": round(march.cargo_food),
            "water": round(march.cargo_water),
        },
    )
    march.cargo_food = 0.0
    march.cargo_water = 0.0
    back = _travel_time_back(march, research_levels(session, march.player_id).get("tunneling", 0))
    now = g.utc_now()
    march.status = "returning"
    march.arrive_at = now
    march.return_at = now + timedelta(seconds=back)


def _resolve_deploy(session, march: March) -> None:
    target = session.get(Nest, march.target_nest_id)
    if target is None or target.player_id != march.player_id:
        march.status = "done"
        return
    add_army(session, target.id, march.units())
    _add_report(
        session,
        march.player_id,
        "deploy",
        f"주둔 완료 → {target.name} ({target.coord})",
        {"to": target.name, "coord": target.coord, "units": march.units()},
    )
    march.status = "done"


_RESOLVERS = {
    g.MARCH_ATTACK: _resolve_attack,
    g.MARCH_SCOUT: _resolve_scout,
    g.MARCH_HUNT: _resolve_hunt,
    g.MARCH_TRANSFER: _resolve_transfer,
    g.MARCH_DEPLOY: _resolve_deploy,
}


def process_due_marches(session) -> int:
    """Resolve arrivals and homecomings that are due. Returns count handled."""
    t_now = g.utc_now()
    handled = 0

    arrivals = session.exec(
        select(March).where(March.status == "outbound", March.arrive_at <= t_now)
    ).all()
    for march in arrivals:
        resolver = _RESOLVERS.get(march.kind)
        if resolver:
            resolver(session, march)
            session.add(march)
            handled += 1

    homecomings = session.exec(
        select(March).where(March.status == "returning", March.return_at <= t_now)
    ).all()
    for march in homecomings:
        home = session.get(Nest, march.from_nest_id)
        if home is not None:
            process_nest(session, home)
            add_army(session, home.id, march.units())
            if march.cargo_food or march.cargo_water:
                cap = g.storage_capacity(
                    get_building_level(session, home.id, "granary")
                )
                home.res_food = min(cap, home.res_food + march.cargo_food)
                home.res_water = min(cap, home.res_water + march.cargo_water)
                session.add(home)
        march.status = "done"
        session.add(march)
        handled += 1

    stale_wars = session.exec(select(War).where(War.active == True, War.ends_at <= t_now)).all()  # noqa: E712
    for w in stale_wars:
        w.active = False
        session.add(w)
        handled += 1
    return handled


def process_all(session) -> None:
    """Background ticker entrypoint: every march, then every player nest."""
    process_due_marches(session)
    players = session.exec(select(Player)).all()
    for player in players:
        process_player(session, player)


# ---------------------------------------------------------------------------
# Creation helpers
# ---------------------------------------------------------------------------


def create_starting_nest(session, player: Player, x: int, y: int, name: str) -> Nest:
    """Create a nest with starter buildings, away from other nests."""
    nest = Nest(
        player_id=player.id,
        name=name,
        x=x,
        y=y,
        is_main=False,
        res_food=g.START_FOOD,
        res_water=g.START_WATER,
        last_tick_at=g.utc_now(),
    )
    session.add(nest)
    session.flush()
    for key, lvl in [
        ("fungus_farm", 1),
        ("dew_collector", 1),
        ("sun_chamber", 1),
        ("granary", 1),
        ("brood_chamber", 1),
    ]:
        session.add(BuildingLevel(nest_id=nest.id, key=key, level=lvl))
    add_army(session, nest.id, {"worker": 8})
    return nest


def find_free_coord(session, rng: random.Random | None = None) -> tuple[int, int]:
    rng = rng or RNG
    occupied = {(n.x, n.y) for n in session.exec(select(Nest)).all()}
    for _ in range(200):
        x, y = rng.randint(2, g.MAP_SIZE - 3), rng.randint(2, g.MAP_SIZE - 3)
        if (x, y) not in occupied:
            return x, y
    raise RuntimeError("map is full")


def is_cell_free(session, x: int, y: int) -> bool:
    row = session.exec(select(Nest).where(Nest.x == x, Nest.y == y)).first()
    return row is None
