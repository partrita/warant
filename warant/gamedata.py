"""WarAnt game data: buildings, units, research, and balance formulas.

All times are in seconds. Costs and durations grow exponentially per
level, production grows super-linearly (OGame-style). Energy is an
action resource: it caps at ENERGY_MAX, is spent by player actions,
and refills over time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Universe settings
# ---------------------------------------------------------------------------

# Global speed multiplier. Higher = faster economy and marches.
UNIVERSE_SPEED = 1.0

# Map is a MAP_SIZE x MAP_SIZE grid of coordinates.
MAP_SIZE = 100

# Maximum nests a player may control (main nest + expansions).
MAX_NESTS = 3

# Cost of founding a new nest (paid from the founding nest's stores).
FOUND_NEST_COST_FOOD = 4_000
FOUND_NEST_COST_WATER = 2_500
FOUND_NEST_WORKERS = 10  # workers consumed as settlers

# Starting resources for a fresh colony.
START_FOOD = 600
START_WATER = 400

# Base protection: colonies under this many points cannot be attacked,
# and nobody can attack players who registered less than this long ago.
NEWBIE_PROTECTION_HOURS = 72
NEWBIE_PROTECTION_POINTS = 5_000

# Alliance war duration once declared.
WAR_DURATION_HOURS = 72

# ---------------------------------------------------------------------------
# Energy (action resource)
# ---------------------------------------------------------------------------
# Energy is NOT produced by buildings. It is spent by player actions
# (upgrades, research, marches...) and refills over time up to ENERGY_MAX.

ENERGY_MAX = 100.0
ENERGY_REGEN_SECONDS = 300.0  # seconds per +1 energy at base speed

# Action costs
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

# Each sun_chamber level speeds up regeneration by this fraction.
SUN_CHAMBER_REGEN_BONUS = 0.10


def energy_regen_rate(sun_level: int) -> float:
    """Energy points gained per hour."""
    base = 3_600.0 / ENERGY_REGEN_SECONDS
    return base * (1.0 + SUN_CHAMBER_REGEN_BONUS * max(0, sun_level))


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Buildings
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


BUILDINGS: dict[str, BuildingDef] = {
    d.key: d
    for d in [
        BuildingDef(
            key="fungus_farm",
            name="버섯 농장",
            desc="곰팡이와 진귀를 길러 먹이를 생산합니다.",
            base_food=60, base_water=30, cost_factor=1.55,
            base_time=50, time_factor=1.62,
            prod_food=32,
        ),
        BuildingDef(
            key="dew_collector",
            name="이슬 수집기",
            desc="아침 이슬을 모아 물을 생산합니다.",
            base_food=70, base_water=40, cost_factor=1.55,
            base_time=55, time_factor=1.62,
            prod_water=28,
        ),
        BuildingDef(
            key="sun_chamber",
            name="양광실",
            desc="여왕의 활력을 되찾아 에너지 회복 속도를 높입니다 (+10%/단계).",
            base_food=45, base_water=15, cost_factor=1.5,
            base_time=40, time_factor=1.58,
        ),
        BuildingDef(
            key="granary",
            name="저장고",
            desc="먹이와 물의 저장 한도를 늘립니다.",
            base_food=80, base_water=60, cost_factor=1.7,
            base_time=45, time_factor=1.6,
            storage=6_000,
        ),
        BuildingDef(
            key="brood_chamber",
            name="육아방",
            desc="알을 돌보개미를 배치해 유닛 생산 속도를 높입니다.",
            base_food=120, base_water=90, cost_factor=1.65,
            base_time=70, time_factor=1.65,
        ),
        BuildingDef(
            key="research_chamber",
            name="연구방",
            desc="여왕의 지혜 저장소. 연구 속도와 단계 상한을 높입니다.",
            base_food=180, base_water=140, cost_factor=1.7,
            base_time=90, time_factor=1.7,
        ),
        BuildingDef(
            key="tunnel_network",
            name="터널망",
            desc="약탈자가 찾지 못하는 숨긴 자원량을 늘립니다.",
            base_food=150, base_water=110, cost_factor=1.7,
            base_time=80, time_factor=1.66,
            one_time_food=500,
        ),
        BuildingDef(
            key="thorn_gate",
            name="가시문",
            desc="입구에 가시를 세워 수비 시 모든 방어력을 강화합니다.",
            base_food=200, base_water=160, cost_factor=1.75,
            base_time=95, time_factor=1.68,
        ),
        BuildingDef(
            key="watch_post",
            name="감시초소",
            desc="정찰대의 은밀성과 적 정찰 저지율을 높입니다.",
            base_food=140, base_water=170, cost_factor=1.7,
            base_time=85, time_factor=1.66,
        ),
    ]
}

BUILDING_ORDER = [
    "fungus_farm", "dew_collector", "sun_chamber", "granary",
    "brood_chamber", "research_chamber", "tunnel_network",
    "thorn_gate", "watch_post",
]


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
    return t / UNIVERSE_SPEED


def building_prod(key: str, level: int) -> tuple[float, float]:
    """(food/hour, water/hour) produced by `key` at `level`."""
    b = BUILDINGS[key]
    if level <= 0:
        return 0.0, 0.0
    food = b.prod_food * level * 1.12 ** (level - 1)
    water = b.prod_water * level * 1.12 ** (level - 1)
    return food, water


def storage_capacity(granary_level: int) -> float:
    """Storage cap for food and water."""
    if granary_level <= 0:
        return 800.0
    g = BUILDINGS["granary"]
    return 800.0 + g.storage * granary_level * 1.35 ** (granary_level - 1)


def hidden_resources(tunnel_level: int) -> float:
    """Resources a raider can never steal (per resource type)."""
    if tunnel_level <= 0:
        return 0.0
    return 500 + 900 * tunnel_level * 1.25 ** (tunnel_level - 1)

# Defense bonus per thorn_gate level.
THORN_GATE_DEF_BONUS = 0.08  # +8% defense per level

# Brood speed bonus per brood_chamber level.
BROOD_SPEED_PER_LEVEL = 0.07  # -7% unit build time per level

# Research speed bonus per research_chamber level.
RESEARCH_SPEED_PER_LEVEL = 0.06  # -6% research time per level

# Max researchable level allowed by research chamber level.
def max_research_level(chamber_level: int) -> int:
    return min(3 + chamber_level * 2, 20)


# ---------------------------------------------------------------------------
# Units (brood) — mobile army and stationary defenses
# ---------------------------------------------------------------------------


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


UNITS: dict[str, UnitDef] = {
    d.key: d
    for d in [
        UnitDef(
            key="worker", name="일개미", desc="먹이를 옮기는 기본 개미. 약하지만 짐꾼입니다.",
            food=50, water=20, build_time=22,
            attack=5, defense=10, hull=30, speed=6, cargo=120,
        ),
        UnitDef(
            key="soldier", name="병정개미", desc="큰턱으로 싸우는 만능 전사.",
            food=150, water=50, build_time=42,
            attack=32, defense=38, hull=110, speed=5, cargo=60,
        ),
        UnitDef(
            key="scout", name="정찰개미", desc="빠르고 은밀합니다. 적 콜로니를 염탐합니다.",
            food=90, water=40, build_time=28,
            attack=3, defense=5, hull=25, speed=14, cargo=20,
            scout_power=12,
        ),
        UnitDef(
            key="flyer", name="비행개미", desc="하늘을 나는 급습 부대. 매우 빠릅니다.",
            food=320, water=220, build_time=75,
            attack=85, defense=40, hull=180, speed=16, cargo=90,
            req_research="chitin", req_research_level=2,
        ),
        UnitDef(
            key="major", name="대형병정", desc="육중한 턱과 판으로 무장한 정예병.",
            food=420, water=160, build_time=88,
            attack=130, defense=105, hull=380, speed=4, cargo=80,
            req_research="mandibles", req_research_level=2,
        ),
        UnitDef(
            key="trap_jaw", name="함정턱개미", desc="턱을 180도로 벌려 폭발적으로 물어뜯는 돌격병.",
            food=850, water=430, build_time=145,
            attack=290, defense=150, hull=520, speed=7, cargo=70,
            req_research="swarm_tactics", req_research_level=2,
        ),
        UnitDef(
            key="acid_ant", name="산개미", desc="몸속에서 산을 뿜어 요새를 녹입니다.",
            food=720, water=650, build_time=135,
            attack=240, defense=190, hull=430, speed=5, cargo=60,
            req_research="hydration", req_research_level=3,
        ),
        # Stationary defenses
        UnitDef(
            key="pit_trap", name="함정 구덩이", desc="적을 빠뜨리는 함정입니다. 움직이지 않습니다.",
            food=110, water=60, build_time=26,
            attack=8, defense=48, hull=60, speed=0, cargo=0,
            is_defense=True,
        ),
        UnitDef(
            key="thorn_pit", name="가시 함정", desc="가시로 뒤덮인 구덩이입니다.",
            food=230, water=120, build_time=44,
            attack=12, defense=115, hull=140, speed=0, cargo=0,
            is_defense=True,
        ),
        UnitDef(
            key="acid_sprayer", name="산 분사구", desc="침입자에게 산을 뿌리는 고정 포탑입니다.",
            food=520, water=340, build_time=78,
            attack=30, defense=300, hull=320, speed=0, cargo=0,
            is_defense=True, req_research="hydration", req_research_level=2,
        ),
    ]
}

UNIT_ORDER = [
    "worker", "soldier", "scout", "flyer", "major", "trap_jaw", "acid_ant",
]
DEFENSE_ORDER = ["pit_trap", "thorn_pit", "acid_sprayer"]

# Wild insects roaming wilderness cells (hunting encounters).
WILD_INSECTS: dict[str, UnitDef] = {
    d.key: d
    for d in [
        UnitDef(key="beetle", name="풍뎅이", desc="", food=0, water=0, build_time=0,
                attack=18, defense=30, hull=90, speed=0, cargo=0),
        UnitDef(key="spider", name="거미", desc="", food=0, water=0, build_time=0,
                attack=42, defense=22, hull=120, speed=0, cargo=0),
        UnitDef(key="wasp", name="말벌", desc="", food=0, water=0, build_time=0,
                attack=65, defense=35, hull=150, speed=0, cargo=0),
        UnitDef(key="mantis", name="사마귀", desc="", food=0, water=0, build_time=0,
                attack=95, defense=55, hull=260, speed=0, cargo=0),
    ]
}


def unit_build_time(key: str, brood_level: int, metabolism_level: int = 0) -> float:
    u = UNITS[key]
    t = u.build_time
    t *= max(0.3, 1.0 - BROOD_SPEED_PER_LEVEL * (brood_level - 1))
    t *= max(0.4, 1.0 - 0.05 * metabolism_level)
    return t / UNIVERSE_SPEED


# ---------------------------------------------------------------------------
# Research
# ---------------------------------------------------------------------------


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


RESEARCH: dict[str, ResearchDef] = {
    d.key: d
    for d in [
        ResearchDef(
            key="foraging", name="채집 기술",
            desc="버섯 농장 생산량 +8% / 단계",
            base_food=200, base_water=100, cost_factor=1.8,
            base_time=420, time_factor=1.75, req_chamber=1,
        ),
        ResearchDef(
            key="hydration", name="수분 관리술",
            desc="이슬 수집기 생산량 +8% / 단계. 산 관련 병종 해금.",
            base_food=240, base_water=180, cost_factor=1.8,
            base_time=480, time_factor=1.75, req_chamber=1,
        ),
        ResearchDef(
            key="metabolism", name="신진대사",
            desc="유닛 생산 시간 -5% / 단계",
            base_food=300, base_water=200, cost_factor=1.85,
            base_time=540, time_factor=1.8, req_chamber=2,
        ),
        ResearchDef(
            key="chitin", name="키틴질 강화",
            desc="모든 유닛 방어력·체력 +8% / 단계. 비행개미 해금.",
            base_food=350, base_water=250, cost_factor=1.85,
            base_time=600, time_factor=1.8, req_chamber=2,
        ),
        ResearchDef(
            key="mandibles", name="대턱 강화",
            desc="모든 유닛 공격력 +8% / 단계. 대형병정 해금.",
            base_food=350, base_water=250, cost_factor=1.85,
            base_time=600, time_factor=1.8, req_chamber=2,
        ),
        ResearchDef(
            key="tunneling", name="굴착 기술",
            desc="진군 이동 시간 -7% / 단계",
            base_food=400, base_water=300, cost_factor=1.9,
            base_time=700, time_factor=1.82, req_chamber=3,
        ),
        ResearchDef(
            key="scent_tracking", name="후각 추적",
            desc="정찰 성공률과 정보 정확도 향상",
            base_food=450, base_water=350, cost_factor=1.9,
            base_time=750, time_factor=1.82, req_chamber=3,
        ),
        ResearchDef(
            key="swarm_tactics", name="군체 전술",
            desc="공격 군세 전투력 +6% / 단계. 함정턱개미 해금.",
            base_food=550, base_water=400, cost_factor=1.95,
            base_time=850, time_factor=1.85, req_chamber=4,
        ),
    ]
}

RESEARCH_ORDER = [
    "foraging", "hydration", "metabolism", "chitin",
    "mandibles", "tunneling", "scent_tracking", "swarm_tactics",
]


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
    return t / UNIVERSE_SPEED


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

HUNT_DURATION_S = 480  # time spent hunting at the target cell
SCOUT_HOLD_S = 60  # scouts linger at target before returning

# Travel: minutes per map cell for a unit of speed 1... units have speed in
# cells/minute already; travel uses slowest unit in the group.
def travel_seconds(distance_cells: float, slowest_speed: int, tunneling_level: int = 0) -> float:
    if slowest_speed <= 0:
        slowest_speed = 1
    mins = distance_cells / slowest_speed
    secs = mins * 60
    secs *= max(0.4, 1.0 - 0.07 * tunneling_level)
    return max(20.0, secs / UNIVERSE_SPEED)


COMBAT_MAX_ROUNDS = 6
COMBAT_VARIANCE = 0.12  # +/- random swing per round
LOOT_EFFICIENCY = 0.75  # fraction of stolen capacity actually filled

# War kill points: attacker kills give score proportional to enemy losses value.
KILL_POINT_DIVISOR = 1_000.0


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
    seconds = max(0, int(seconds))
    d, rem = divmod(seconds, 86_400)
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
