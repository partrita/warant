"""WarAnt game data: buildings, units, research, and balance formulas.

All times are in seconds. Costs and durations grow exponentially per
level, production grows super-linearly (OGame-style). Energy is an
action resource: it caps at ENERGY_MAX, is spent by player actions,
and refills over time.

Balance values and stats are loaded from `balance_config.json` (or WARANT_BALANCE_CONFIG),
making it easy to tune unit stats, building growth rates, times, and formulas in one place.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# Path to the balance configuration file
BALANCE_CONFIG_FILE = os.getenv(
    "WARANT_BALANCE_CONFIG",
    os.path.join(os.path.dirname(__file__), "balance_config.json"),
)

# ---------------------------------------------------------------------------
# Universe settings & Test Mode
# ---------------------------------------------------------------------------

UNIVERSE_SPEED = 1.0
TEST_MODE: bool = os.getenv("WARANT_TEST_MODE", "0").lower() in ("1", "true", "yes")
TEST_SPEED_MULTIPLIER: float = 1000.0

MAP_SIZE = 100
MAX_NESTS = 3
FOUND_NEST_COST_FOOD = 4_000
FOUND_NEST_COST_WATER = 2_500
FOUND_NEST_WORKERS = 10
START_FOOD = 600
START_WATER = 400
NEWBIE_PROTECTION_HOURS = 72
NEWBIE_PROTECTION_POINTS = 5_000
WAR_DURATION_HOURS = 72

# Energy (action resource)
ENERGY_MAX = 100.0
ENERGY_REGEN_SECONDS = 300.0
SUN_CHAMBER_REGEN_BONUS = 0.10

COST_BUILD_UPGRADE = 8.0
COST_RESEARCH_START = 12.0
COST_BROOD_BATCH = 4.0
COST_MARCH_ATTACK = 20.0
COST_MARCH_SCOUT = 8.0
COST_MARCH_HUNT = 10.0
COST_MARCH_TRANSFER = 6.0
COST_MARCH_DEPLOY = 6.0
COST_FOUND_NEST = 30.0
COST_DECLARE_WAR = 25.0

# Growth & Formula multipliers
THORN_GATE_DEF_BONUS = 0.08
BROOD_SPEED_PER_LEVEL = 0.07
RESEARCH_SPEED_PER_LEVEL = 0.06
PROD_GROWTH_BASE = 1.12
STORAGE_GROWTH_BASE = 1.35
BASE_STORAGE = 800.0
TUNNEL_BASE_HIDDEN = 500.0
TUNNEL_GROWTH_STEP = 900.0
TUNNEL_GROWTH_BASE = 1.25

BASE_ANT_CAP = 50
ANT_CAP_PER_HOUSING = 30

HUNT_DURATION_S = 480
SCOUT_HOLD_S = 60
COMBAT_MAX_ROUNDS = 6
COMBAT_VARIANCE = 0.12
LOOT_EFFICIENCY = 0.75
KILL_POINT_DIVISOR = 1_000.0


def is_test_mode() -> bool:
    return TEST_MODE


def set_test_mode(enabled: bool) -> None:
    global TEST_MODE
    TEST_MODE = enabled


def get_speed_multiplier() -> float:
    return TEST_SPEED_MULTIPLIER if TEST_MODE else 1.0


def energy_regen_rate(sun_level: int) -> float:
    """Energy points gained per hour."""
    base = (3_600.0 / ENERGY_REGEN_SECONDS) * get_speed_multiplier()
    return base * (1.0 + SUN_CHAMBER_REGEN_BONUS * max(0, sun_level))


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BuildingDef:
    key: str
    name: str
    desc: str
    base_food: float  # level-1 cost in food
    base_water: float  # level-1 cost in water
    cost_factor: float  # cost growth per level
    base_time: float  # level-1 build time in seconds
    time_factor: float  # build-time growth per level
    max_level: int = 30
    prod_food: float = 0.0  # food/hour at level 1 (super-linear growth)
    prod_water: float = 0.0
    storage: float = 0.0  # extra storage per level for food & water
    one_time_food: float = 0.0  # flat capacity added at any level >= 1


@dataclass(frozen=True)
class UnitDef:
    key: str
    name: str
    desc: str
    food: float
    water: float
    build_time: float  # seconds at brood_chamber level 1
    attack: int
    defense: int
    hull: int  # hit points
    speed: int  # map cells per minute; 0 = stationary defense
    cargo: int  # resources carried
    is_defense: bool = False
    scout_power: int = 0  # espionage strength
    req_research: str | None = None
    req_research_level: int = 0


@dataclass(frozen=True)
class ResearchDef:
    key: str
    name: str
    desc: str
    base_food: float
    base_water: float
    cost_factor: float
    base_time: float  # seconds at level 1
    time_factor: float
    req_chamber: int  # required research_chamber level
    req_research: str | None = None
    req_research_level: int = 0


# In-memory balance tables
BUILDINGS: dict[str, BuildingDef] = {}
BUILDING_ORDER: list[str] = [
    "fungus_farm", "dew_collector", "sun_chamber", "granary",
    "living_quarters", "brood_chamber", "research_chamber", "tunnel_network",
    "thorn_gate", "watch_post",
]

UNITS: dict[str, UnitDef] = {}
UNIT_ORDER: list[str] = [
    "worker", "soldier", "scout", "flyer", "major", "trap_jaw", "acid_ant",
]
DEFENSE_ORDER: list[str] = ["pit_trap", "thorn_pit", "acid_sprayer"]

WILD_INSECTS: dict[str, UnitDef] = {}

RESEARCH: dict[str, ResearchDef] = {}
RESEARCH_ORDER: list[str] = [
    "foraging", "hydration", "metabolism", "chitin",
    "mandibles", "tunneling", "scent_tracking", "swarm_tactics",
]


# ---------------------------------------------------------------------------
# Balance Loader & Saver
# ---------------------------------------------------------------------------


def load_balance_config(path: str | None = None) -> bool:
    """Load balance values from JSON file into global tables and settings."""
    global UNIVERSE_SPEED, MAP_SIZE, MAX_NESTS, START_FOOD, START_WATER
    global FOUND_NEST_COST_FOOD, FOUND_NEST_COST_WATER, FOUND_NEST_WORKERS
    global NEWBIE_PROTECTION_HOURS, NEWBIE_PROTECTION_POINTS, WAR_DURATION_HOURS
    global ENERGY_MAX, ENERGY_REGEN_SECONDS, SUN_CHAMBER_REGEN_BONUS
    global COST_BUILD_UPGRADE, COST_RESEARCH_START, COST_BROOD_BATCH
    global COST_MARCH_ATTACK, COST_MARCH_SCOUT, COST_MARCH_HUNT
    global COST_MARCH_TRANSFER, COST_MARCH_DEPLOY, COST_FOUND_NEST, COST_DECLARE_WAR
    global THORN_GATE_DEF_BONUS, BROOD_SPEED_PER_LEVEL, RESEARCH_SPEED_PER_LEVEL
    global PROD_GROWTH_BASE, STORAGE_GROWTH_BASE, BASE_STORAGE
    global TUNNEL_BASE_HIDDEN, TUNNEL_GROWTH_STEP, TUNNEL_GROWTH_BASE
    global BASE_ANT_CAP, ANT_CAP_PER_HOUSING
    global HUNT_DURATION_S, SCOUT_HOLD_S, COMBAT_MAX_ROUNDS, COMBAT_VARIANCE, LOOT_EFFICIENCY, KILL_POINT_DIVISOR
    global BUILDINGS, UNITS, WILD_INSECTS, RESEARCH

    cfg_path = path or BALANCE_CONFIG_FILE
    if not os.path.exists(cfg_path):
        logger.warning("Balance config file '%s' not found, initializing default.", cfg_path)
        _init_defaults()
        save_balance_config(cfg_path)
        return True

    try:
        with open(cfg_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as e:
        logger.error("Failed to parse balance config '%s': %s. Using defaults.", cfg_path, e)
        _init_defaults()
        return False

    # 1. Load Settings
    settings = data.get("settings", {})
    UNIVERSE_SPEED = float(settings.get("universe_speed", UNIVERSE_SPEED))
    MAP_SIZE = int(settings.get("map_size", MAP_SIZE))
    MAX_NESTS = int(settings.get("max_nests", MAX_NESTS))
    START_FOOD = float(settings.get("start_food", START_FOOD))
    START_WATER = float(settings.get("start_water", START_WATER))
    FOUND_NEST_COST_FOOD = float(settings.get("found_nest_cost_food", FOUND_NEST_COST_FOOD))
    FOUND_NEST_COST_WATER = float(settings.get("found_nest_cost_water", FOUND_NEST_COST_WATER))
    FOUND_NEST_WORKERS = int(settings.get("found_nest_workers", FOUND_NEST_WORKERS))
    NEWBIE_PROTECTION_HOURS = int(settings.get("newbie_protection_hours", NEWBIE_PROTECTION_HOURS))
    NEWBIE_PROTECTION_POINTS = int(settings.get("newbie_protection_points", NEWBIE_PROTECTION_POINTS))
    WAR_DURATION_HOURS = int(settings.get("war_duration_hours", WAR_DURATION_HOURS))

    ENERGY_MAX = float(settings.get("energy_max", ENERGY_MAX))
    ENERGY_REGEN_SECONDS = float(settings.get("energy_regen_seconds", ENERGY_REGEN_SECONDS))
    SUN_CHAMBER_REGEN_BONUS = float(settings.get("sun_chamber_regen_bonus", SUN_CHAMBER_REGEN_BONUS))

    COST_BUILD_UPGRADE = float(settings.get("cost_build_upgrade", COST_BUILD_UPGRADE))
    COST_RESEARCH_START = float(settings.get("cost_research_start", COST_RESEARCH_START))
    COST_BROOD_BATCH = float(settings.get("cost_brood_batch", COST_BROOD_BATCH))
    COST_MARCH_ATTACK = float(settings.get("cost_march_attack", COST_MARCH_ATTACK))
    COST_MARCH_SCOUT = float(settings.get("cost_march_scout", COST_MARCH_SCOUT))
    COST_MARCH_HUNT = float(settings.get("cost_march_hunt", COST_MARCH_HUNT))
    COST_MARCH_TRANSFER = float(settings.get("cost_march_transfer", COST_MARCH_TRANSFER))
    COST_MARCH_DEPLOY = float(settings.get("cost_march_deploy", COST_MARCH_DEPLOY))
    COST_FOUND_NEST = float(settings.get("cost_found_nest", COST_FOUND_NEST))
    COST_DECLARE_WAR = float(settings.get("cost_declare_war", COST_DECLARE_WAR))

    THORN_GATE_DEF_BONUS = float(settings.get("thorn_gate_def_bonus", THORN_GATE_DEF_BONUS))
    BROOD_SPEED_PER_LEVEL = float(settings.get("brood_speed_per_level", BROOD_SPEED_PER_LEVEL))
    RESEARCH_SPEED_PER_LEVEL = float(settings.get("research_speed_per_level", RESEARCH_SPEED_PER_LEVEL))
    PROD_GROWTH_BASE = float(settings.get("prod_growth_base", PROD_GROWTH_BASE))
    STORAGE_GROWTH_BASE = float(settings.get("storage_growth_base", STORAGE_GROWTH_BASE))
    BASE_STORAGE = float(settings.get("base_storage", BASE_STORAGE))
    TUNNEL_BASE_HIDDEN = float(settings.get("tunnel_base_hidden", TUNNEL_BASE_HIDDEN))
    TUNNEL_GROWTH_STEP = float(settings.get("tunnel_growth_step", TUNNEL_GROWTH_STEP))
    TUNNEL_GROWTH_BASE = float(settings.get("tunnel_growth_base", TUNNEL_GROWTH_BASE))
    BASE_ANT_CAP = int(settings.get("base_ant_cap", BASE_ANT_CAP))
    ANT_CAP_PER_HOUSING = int(settings.get("ant_cap_per_housing", ANT_CAP_PER_HOUSING))

    HUNT_DURATION_S = int(settings.get("hunt_duration_s", HUNT_DURATION_S))
    SCOUT_HOLD_S = int(settings.get("scout_hold_s", SCOUT_HOLD_S))
    COMBAT_MAX_ROUNDS = int(settings.get("combat_max_rounds", COMBAT_MAX_ROUNDS))
    COMBAT_VARIANCE = float(settings.get("combat_variance", COMBAT_VARIANCE))
    LOOT_EFFICIENCY = float(settings.get("loot_efficiency", LOOT_EFFICIENCY))
    KILL_POINT_DIVISOR = float(settings.get("kill_point_divisor", KILL_POINT_DIVISOR))

    # 2. Load Buildings
    buildings_data = data.get("buildings", {})
    new_buildings = {}
    for key, b in buildings_data.items():
        new_buildings[key] = BuildingDef(
            key=key,
            name=b.get("name", key),
            desc=b.get("desc", ""),
            base_food=float(b.get("base_food", 0)),
            base_water=float(b.get("base_water", 0)),
            cost_factor=float(b.get("cost_factor", 1.5)),
            base_time=float(b.get("base_time", 60)),
            time_factor=float(b.get("time_factor", 1.6)),
            max_level=int(b.get("max_level", 30)),
            prod_food=float(b.get("prod_food", 0)),
            prod_water=float(b.get("prod_water", 0)),
            storage=float(b.get("storage", 0)),
            one_time_food=float(b.get("one_time_food", 0)),
        )
    BUILDINGS = new_buildings

    # 3. Load Units
    units_data = data.get("units", {})
    new_units = {}
    for key, u in units_data.items():
        new_units[key] = UnitDef(
            key=key,
            name=u.get("name", key),
            desc=u.get("desc", ""),
            food=float(u.get("food", 0)),
            water=float(u.get("water", 0)),
            build_time=float(u.get("build_time", 30)),
            attack=int(u.get("attack", 0)),
            defense=int(u.get("defense", 0)),
            hull=int(u.get("hull", 10)),
            speed=int(u.get("speed", 0)),
            cargo=int(u.get("cargo", 0)),
            is_defense=bool(u.get("is_defense", False)),
            scout_power=int(u.get("scout_power", 0)),
            req_research=u.get("req_research"),
            req_research_level=int(u.get("req_research_level", 0)),
        )
    UNITS = new_units

    # 4. Load Wild Insects
    wild_data = data.get("wild_insects", {})
    new_wild = {}
    for key, w in wild_data.items():
        new_wild[key] = UnitDef(
            key=key,
            name=w.get("name", key),
            desc=w.get("desc", ""),
            food=float(w.get("food", 0)),
            water=float(w.get("water", 0)),
            build_time=float(w.get("build_time", 0)),
            attack=int(w.get("attack", 0)),
            defense=int(w.get("defense", 0)),
            hull=int(w.get("hull", 10)),
            speed=int(w.get("speed", 0)),
            cargo=int(w.get("cargo", 0)),
            is_defense=False,
            scout_power=0,
            req_research=None,
            req_research_level=0,
        )
    WILD_INSECTS = new_wild

    # 5. Load Research
    research_data = data.get("research", {})
    new_research = {}
    for key, r in research_data.items():
        new_research[key] = ResearchDef(
            key=key,
            name=r.get("name", key),
            desc=r.get("desc", ""),
            base_food=float(r.get("base_food", 0)),
            base_water=float(r.get("base_water", 0)),
            cost_factor=float(r.get("cost_factor", 1.8)),
            base_time=float(r.get("base_time", 300)),
            time_factor=float(r.get("time_factor", 1.8)),
            req_chamber=int(r.get("req_chamber", 1)),
            req_research=r.get("req_research"),
            req_research_level=int(r.get("req_research_level", 0)),
        )
    RESEARCH = new_research
    return True


def save_balance_config(path: str | None = None) -> None:
    """Save the in-memory balance configuration to a formatted JSON file."""
    cfg_path = path or BALANCE_CONFIG_FILE
    data = {
        "version": 1,
        "description": "WarAnt Game Balance Configuration - Edit stats, costs, formulas and growth rates here",
        "settings": {
            "universe_speed": UNIVERSE_SPEED,
            "map_size": MAP_SIZE,
            "max_nests": MAX_NESTS,
            "start_food": START_FOOD,
            "start_water": START_WATER,
            "found_nest_cost_food": FOUND_NEST_COST_FOOD,
            "found_nest_cost_water": FOUND_NEST_COST_WATER,
            "found_nest_workers": FOUND_NEST_WORKERS,
            "newbie_protection_hours": NEWBIE_PROTECTION_HOURS,
            "newbie_protection_points": NEWBIE_PROTECTION_POINTS,
            "war_duration_hours": WAR_DURATION_HOURS,
            "energy_max": ENERGY_MAX,
            "energy_regen_seconds": ENERGY_REGEN_SECONDS,
            "sun_chamber_regen_bonus": SUN_CHAMBER_REGEN_BONUS,
            "cost_build_upgrade": COST_BUILD_UPGRADE,
            "cost_research_start": COST_RESEARCH_START,
            "cost_brood_batch": COST_BROOD_BATCH,
            "cost_march_attack": COST_MARCH_ATTACK,
            "cost_march_scout": COST_MARCH_SCOUT,
            "cost_march_hunt": COST_MARCH_HUNT,
            "cost_march_transfer": COST_MARCH_TRANSFER,
            "cost_march_deploy": COST_MARCH_DEPLOY,
            "cost_found_nest": COST_FOUND_NEST,
            "cost_declare_war": COST_DECLARE_WAR,
            "thorn_gate_def_bonus": THORN_GATE_DEF_BONUS,
            "brood_speed_per_level": BROOD_SPEED_PER_LEVEL,
            "research_speed_per_level": RESEARCH_SPEED_PER_LEVEL,
            "prod_growth_base": PROD_GROWTH_BASE,
            "storage_growth_base": STORAGE_GROWTH_BASE,
            "base_storage": BASE_STORAGE,
            "tunnel_base_hidden": TUNNEL_BASE_HIDDEN,
            "tunnel_growth_step": TUNNEL_GROWTH_STEP,
            "tunnel_growth_base": TUNNEL_GROWTH_BASE,
            "base_ant_cap": BASE_ANT_CAP,
            "ant_cap_per_housing": ANT_CAP_PER_HOUSING,
            "hunt_duration_s": HUNT_DURATION_S,
            "scout_hold_s": SCOUT_HOLD_S,
            "combat_max_rounds": COMBAT_MAX_ROUNDS,
            "combat_variance": COMBAT_VARIANCE,
            "loot_efficiency": LOOT_EFFICIENCY,
            "kill_point_divisor": KILL_POINT_DIVISOR,
        },
        "units": {
            k: {
                "name": u.name,
                "desc": u.desc,
                "food": u.food,
                "water": u.water,
                "build_time": u.build_time,
                "attack": u.attack,
                "defense": u.defense,
                "hull": u.hull,
                "speed": u.speed,
                "cargo": u.cargo,
                "is_defense": u.is_defense,
                "scout_power": u.scout_power,
                "req_research": u.req_research,
                "req_research_level": u.req_research_level,
            }
            for k, u in UNITS.items()
        },
        "buildings": {
            k: {
                "name": b.name,
                "desc": b.desc,
                "base_food": b.base_food,
                "base_water": b.base_water,
                "cost_factor": b.cost_factor,
                "base_time": b.base_time,
                "time_factor": b.time_factor,
                "max_level": b.max_level,
                "prod_food": b.prod_food,
                "prod_water": b.prod_water,
                "storage": b.storage,
                "one_time_food": b.one_time_food,
            }
            for k, b in BUILDINGS.items()
        },
        "research": {
            k: {
                "name": r.name,
                "desc": r.desc,
                "base_food": r.base_food,
                "base_water": r.base_water,
                "cost_factor": r.cost_factor,
                "base_time": r.base_time,
                "time_factor": r.time_factor,
                "req_chamber": r.req_chamber,
                "req_research": r.req_research,
                "req_research_level": r.req_research_level,
            }
            for k, r in RESEARCH.items()
        },
        "wild_insects": {
            k: {
                "name": w.name,
                "desc": w.desc,
                "food": w.food,
                "water": w.water,
                "build_time": w.build_time,
                "attack": w.attack,
                "defense": w.defense,
                "hull": w.hull,
                "speed": w.speed,
                "cargo": w.cargo,
                "is_defense": w.is_defense,
                "scout_power": w.scout_power,
                "req_research": w.req_research,
                "req_research_level": w.req_research_level,
            }
            for k, w in WILD_INSECTS.items()
        },
    }
    os.makedirs(os.path.dirname(os.path.abspath(cfg_path)), exist_ok=True)
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def reload_balance(path: str | None = None) -> bool:
    """Reload balance values from the configuration file on disk."""
    return load_balance_config(path or BALANCE_CONFIG_FILE)


def _init_defaults():
    """Built-in hardcoded fallback defaults if JSON file is missing."""
    global BUILDINGS, UNITS, WILD_INSECTS, RESEARCH
    BUILDINGS = {
        "fungus_farm": BuildingDef("fungus_farm", "버섯 농장", "곰팡이와 진귀를 길러 먹이를 생산합니다.", 60, 30, 1.55, 50, 1.62, 30, 32, 0, 0, 0),
        "dew_collector": BuildingDef("dew_collector", "이슬 수집기", "아침 이슬을 모아 물을 생산합니다.", 70, 40, 1.55, 55, 1.62, 30, 0, 28, 0, 0),
        "sun_chamber": BuildingDef("sun_chamber", "양광실", "여왕의 활력을 되찾아 에너지 회복 속도를 높입니다 (+10%/단계).", 45, 15, 1.5, 40, 1.58, 30),
        "granary": BuildingDef("granary", "저장고", "먹이와 물의 저장 한도를 늘립니다.", 80, 60, 1.7, 45, 1.6, 30, 0, 0, 6000, 0),
        "living_quarters": BuildingDef("living_quarters", "개미 숙소", "개미들의 생활 공간을 확장하여 둥지의 최대 개미 수용 한도를 늘립니다 (+30/단계).", 100, 75, 1.6, 60, 1.6, 30),
        "brood_chamber": BuildingDef("brood_chamber", "육아방", "알을 돌보개미를 배치해 유닛 생산 속도를 높입니다.", 120, 90, 1.65, 70, 1.65, 30),
        "research_chamber": BuildingDef("research_chamber", "연구방", "여왕의 지혜 저장소. 연구 속도와 단계 상한을 높입니다.", 180, 140, 1.7, 90, 1.7, 30),
        "tunnel_network": BuildingDef("tunnel_network", "터널망", "약탈자가 찾지 못하는 숨긴 자원량을 늘립니다.", 150, 110, 1.7, 80, 1.66, 30, 0, 0, 0, 500),
        "thorn_gate": BuildingDef("thorn_gate", "가시문", "입구에 가시를 세워 수비 시 모든 방어력을 강화합니다.", 200, 160, 1.75, 95, 1.68, 30),
        "watch_post": BuildingDef("watch_post", "감시초소", "정찰대의 은밀성과 적 정찰 저지율을 높입니다.", 140, 170, 1.7, 85, 1.66, 30),
    }
    UNITS = {
        "worker": UnitDef("worker", "일개미", "먹이를 옮기는 기본 개미. 약하지만 짐꾼입니다.", 50, 20, 22, 5, 10, 30, 6, 120),
        "soldier": UnitDef("soldier", "병정개미", "큰턱으로 싸우는 만능 전사.", 150, 50, 42, 32, 38, 110, 5, 60),
        "scout": UnitDef("scout", "정찰개미", "빠르고 은밀합니다. 적 둥지를 염탐합니다.", 90, 40, 28, 3, 5, 25, 14, 20, scout_power=12),
        "flyer": UnitDef("flyer", "비행개미", "하늘을 나는 급습 부대. 매우 빠릅니다.", 320, 220, 75, 85, 40, 180, 16, 90, req_research="chitin", req_research_level=2),
        "major": UnitDef("major", "대형병정", "육중한 턱과 판으로 무장한 정예병.", 420, 160, 88, 130, 105, 380, 4, 80, req_research="mandibles", req_research_level=2),
        "trap_jaw": UnitDef("trap_jaw", "함정턱개미", "턱을 180도로 벌려 폭발적으로 물어뜯는 돌격병.", 850, 430, 145, 290, 150, 520, 7, 70, req_research="swarm_tactics", req_research_level=2),
        "acid_ant": UnitDef("acid_ant", "산개미", "몸속에서 산을 뿜어 요새를 녹입니다.", 720, 650, 135, 240, 190, 430, 5, 60, req_research="hydration", req_research_level=3),
        "pit_trap": UnitDef("pit_trap", "함정 구덩이", "적을 빠뜨리는 함정입니다. 움직이지 않습니다.", 110, 60, 26, 8, 48, 60, 0, 0, is_defense=True),
        "thorn_pit": UnitDef("thorn_pit", "가시 함정", "가시로 뒤덮인 구덩이입니다.", 230, 120, 44, 12, 115, 140, 0, 0, is_defense=True),
        "acid_sprayer": UnitDef("acid_sprayer", "산 분사구", "침입자에게 산을 뿌리는 고정 포탑입니다.", 520, 340, 78, 30, 300, 320, 0, 0, is_defense=True, req_research="hydration", req_research_level=2),
    }
    WILD_INSECTS = {
        "beetle": UnitDef("beetle", "풍뎅이", "단단한 껍질을 가진 야생 풍뎅이.", 0, 0, 0, 18, 30, 90, 0, 0),
        "spider": UnitDef("spider", "거미", "날카로운 독니를 가진 야생 거미.", 0, 0, 0, 42, 22, 120, 0, 0),
        "wasp": UnitDef("wasp", "말벌", "하늘에서 급습하는 위협적인 야생 말벌.", 0, 0, 0, 65, 35, 150, 0, 0),
        "mantis": UnitDef("mantis", "사마귀", "거대한 낫을 휘두르는 최상위 포식자.", 0, 0, 0, 95, 55, 260, 0, 0),
    }
    RESEARCH = {
        "foraging": ResearchDef("foraging", "채집 기술", "버섯 농장 생산량 +8% / 단계", 200, 100, 1.8, 420, 1.75, 1),
        "hydration": ResearchDef("hydration", "수분 관리술", "이슬 수집기 생산량 +8% / 단계. 산 관련 병종 해금.", 240, 180, 1.8, 480, 1.75, 1),
        "metabolism": ResearchDef("metabolism", "신진대사", "유닛 생산 시간 -5% / 단계", 300, 200, 1.85, 540, 1.8, 2),
        "chitin": ResearchDef("chitin", "키틴질 강화", "모든 유닛 방어력·체력 +8% / 단계. 비행개미 해금.", 350, 250, 1.85, 600, 1.8, 2),
        "mandibles": ResearchDef("mandibles", "턱 강화", "모든 유닛 공격력 +8% / 단계. 대형병정 해금.", 350, 250, 1.85, 600, 1.8, 2),
        "tunneling": ResearchDef("tunneling", "굴착 기술", "진군 이동 시간 -7% / 단계", 400, 300, 1.9, 700, 1.82, 3),
        "scent_tracking": ResearchDef("scent_tracking", "후각 추적", "정찰 성공률과 정보 정확도 향상", 450, 350, 1.9, 750, 1.82, 3),
        "swarm_tactics": ResearchDef("swarm_tactics", "군체 전술", "공격 군세 전투력 +6% / 단계. 함정턱개미 해금.", 550, 400, 1.95, 850, 1.85, 4),
    }


# Initial load upon import
load_balance_config()


# ---------------------------------------------------------------------------
# Balance Formulas
# ---------------------------------------------------------------------------


def ant_population_cap(housing_level: int) -> int:
    """Maximum mobile ants this colony can support based on living_quarters building level."""
    return int(BASE_ANT_CAP + ANT_CAP_PER_HOUSING * max(0, housing_level))


def building_cost(key: str, target_level: int) -> tuple[float, float]:
    """Cost (food, water) to upgrade `key` to `target_level`."""
    b = BUILDINGS[key]
    f = b.base_food * b.cost_factor ** (target_level - 1)
    w = b.base_water * b.cost_factor ** (target_level - 1)
    return f, w


def building_time(key: str, target_level: int) -> float:
    """Seconds to upgrade `key` to `target_level`."""
    b = BUILDINGS[key]
    t = b.base_time * b.time_factor ** (target_level - 1)
    return t / (UNIVERSE_SPEED * get_speed_multiplier())


def building_prod(key: str, level: int) -> tuple[float, float]:
    """(food/hour, water/hour) produced by `key` at `level`."""
    b = BUILDINGS[key]
    if level <= 0:
        return 0.0, 0.0
    food = b.prod_food * level * (PROD_GROWTH_BASE ** (level - 1))
    water = b.prod_water * level * (PROD_GROWTH_BASE ** (level - 1))
    return food, water


def storage_capacity(granary_level: int) -> float:
    """Storage cap for food and water."""
    if granary_level <= 0:
        return BASE_STORAGE
    g = BUILDINGS["granary"]
    return BASE_STORAGE + g.storage * granary_level * (STORAGE_GROWTH_BASE ** (granary_level - 1))


def hidden_resources(tunnel_level: int) -> float:
    """Resources a raider can never steal (per resource type)."""
    if tunnel_level <= 0:
        return 0.0
    return TUNNEL_BASE_HIDDEN + TUNNEL_GROWTH_STEP * tunnel_level * (TUNNEL_GROWTH_BASE ** (tunnel_level - 1))


def max_research_level(chamber_level: int) -> int:
    return min(3 + chamber_level * 2, 20)


def unit_build_time(key: str, brood_level: int, metabolism_level: int = 0) -> float:
    u = UNITS[key]
    t = u.build_time
    t *= max(0.3, 1.0 - BROOD_SPEED_PER_LEVEL * (brood_level - 1))
    t *= max(0.4, 1.0 - 0.05 * metabolism_level)
    return t / (UNIVERSE_SPEED * get_speed_multiplier())


def research_cost(key: str, target_level: int) -> tuple[float, float]:
    r = RESEARCH[key]
    return (
        r.base_food * r.cost_factor ** (target_level - 1),
        r.base_water * r.cost_factor ** (target_level - 1),
    )


def research_time(key: str, target_level: int, chamber_level: int) -> float:
    r = RESEARCH[key]
    t = r.base_time * r.time_factor ** (target_level - 1)
    t *= max(0.3, 1.0 - RESEARCH_SPEED_PER_LEVEL * (chamber_level - 1))
    return t / (UNIVERSE_SPEED * get_speed_multiplier())


# ---------------------------------------------------------------------------
# Marches & combat
# ---------------------------------------------------------------------------

MARCH_ATTACK = "attack"
MARCH_SCOUT = "scout"
MARCH_HUNT = "hunt"
MARCH_TRANSFER = "transfer"
MARCH_DEPLOY = "deploy"

MARCH_NAMES = {
    MARCH_ATTACK: "공격",
    MARCH_SCOUT: "정찰",
    MARCH_HUNT: "사냥",
    MARCH_TRANSFER: "이송",
    MARCH_DEPLOY: "주둔",
}


def travel_seconds(distance_cells: float, slowest_speed: int, tunneling_level: int = 0) -> float:
    if slowest_speed <= 0:
        slowest_speed = 1
    mins = distance_cells / slowest_speed
    secs = mins * 60
    secs *= max(0.4, 1.0 - 0.07 * tunneling_level)
    speed = UNIVERSE_SPEED * get_speed_multiplier()
    min_sec = 0.5 if TEST_MODE else 20.0
    return max(min_sec, secs / speed)


# ---------------------------------------------------------------------------
# Points (ranking)
# ---------------------------------------------------------------------------


def unit_points(key: str) -> float:
    u = UNITS.get(key) or WILD_INSECTS.get(key)
    if not u:
        return 0.0
    return (u.food + u.water) / 1_000.0


def building_points(key: str, level: int) -> float:
    total = 0.0
    for lvl in range(1, level + 1):
        f, w = building_cost(key, lvl)
        total += f + w
    return total / 1_000.0


def research_points(key: str, level: int) -> float:
    total = 0.0
    for lvl in range(1, level + 1):
        f, w = research_cost(key, lvl)
        total += f + w
    return total / 1_000.0


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def fmt_num(n: float) -> str:
    n = float(n)
    if abs(n) >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if abs(n) >= 10_000:
        return f"{n / 1_000:.1f}k"
    return f"{n:,.0f}"


def fmt_duration(seconds: float) -> str:
    if seconds <= 0:
        return "0초"
    if seconds < 1.0:
        return f"{seconds:.2f}초"
    sec_int = int(seconds)
    d, rem = divmod(sec_int, 86_400)
    h, rem = divmod(rem, 3_600)
    m, s = divmod(rem, 60)
    if d:
        return f"{d}일 {h}시간 {m}분"
    if h:
        return f"{h}시간 {m}분 {s}초"
    if m:
        return f"{m}분 {s}초"
    return f"{s}초"


def fmt_coord(x: int, y: int) -> str:
    return f"[{x}:{y}]"
