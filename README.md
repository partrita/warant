# WarAnt 👑🐜

**WarAnt** is a real-time multiplayer browser strategy game where you play as an **ant queen**, inspired by classic 4X space strategy games like OGame. Expand your underground nest, build mushroom farms and dew collectors, hatch specialized ant castes, scout and hunt dangerous wild insects, raid rival colonies, and wage epic 72-hour alliance wars.

[한국어 README](README.ko.md)

<p align="center">
  <img src="warant_sceenshot.jpg.png" alt="WarAnt Mobile-First Nest View Screenshot" width="380" />
</p>

<p align="center">
  <em>Mobile-first responsive UI with real-time animated pixel-art underground nest</em>
</p>

---

## 🌟 Key Features

### 🏰 Colony Management & Economy
- **Real-Time Colony Economy** — Food (🍒) and Water (💧) accumulate passively, capped by Granary storage.
- **Action Energy (⚡)** — Upgrades, brood hatching, research, and marches consume energy (max 100) that refills over time (boosted by the Sun Chamber).
- **Living Quarters & Population Cap** — Upgrade **Living Quarters (개미 숙소)** to expand your nest's ant capacity.
- **Queue & Refund System** — Cancel in-progress construction or brood batches anytime with a **50% resource refund**.
- **Underground Pixel Animation** — Dynamic animated cross-section GIF that evolves as your colony grows from a tiny mound to a bustling ant empire.

### 🐜 Brood Chamber & Castes
- **Batch Hatching with Smart Slider** — Choose hatch quantities with an interactive slider that automatically calculates max affordable ants based on current resources and housing space.
- **7 Specialized Ant Units**:
  - 🐜 **Worker Ant (일개미)**: Efficient resource foraging and carrying capacity.
  - ⚔️ **Soldier Ant (병정개미)**: Fast, balanced frontline infantry.
  - 👁️ **Scout Ant (정찰개미)**: High-speed reconnaissance unit for spying on nests and wild territories.
  - 🪽 **Flyer (비행개미)**: Rapid aerial raider capable of swift strikes.
  - 🛡️ **Major Ant (대형병정)**: Heavy armor and devastating siege strength.
  - 💥 **Trap-Jaw Ant (함정턱개미)**: High-burst ambush predator.
  - 🧪 **Acid Ant (산개미)**: Ranged acid spitter that bypasses heavy carapace.

### 🗺️ World Map & Exploration (100×100 Grid)
- **Wild Scouting (야생 정찰)** — Send scout ants into the wilderness to investigate wild insect nests. Scouting success and intel detail (insect numbers and wild resources) scale with your scout count, with realistic casualty risks on dangerous missions.
- **Insect Hunting (야생 사냥)** — Deploy armies to hunt beetles, spiders, wasps, and mantises for massive food and water bounties.
- **Nest Raids & Recon** — Attack enemy queens to plunder unhidden resources or scout their defenses.
- **Garrison & Transfers** — Relocate troops and transfer resources between allied or own nests.

### ⚔️ Tactical Combat & Defense
- **Round-Based Battle Simulation** — Calculates casualties using unit stats, research bonuses, and defensive fortifications.
- **Thorn Gates & Pit Traps** — Fortify your nest against invaders.
- **Tunnel Networks (터널망)** — Safeguard a portion of your resources from enemy raids.
- **Newbie Protection** — Safe harbor for newly founded nests.

### 🤝 Alliances & Wars
- **Alliances** — Found or join alliances, coordinate garrisons, and share intel.
- **72-Hour Alliance Wars** — Declare war with a +25% combat buff and battle kill-point leaderboard.
- **Global Rankings** — Compete for supremacy across individual and alliance leaderboards.

---

## 🛠️ Tech Stack

| Layer | Technology |
| --- | --- |
| **Full-Stack Framework** | [Reflex](https://reflex.dev) (Pure Python → React/Next.js) |
| **Database & ORM** | SQLModel / SQLAlchemy (SQLite default, PostgreSQL supported) |
| **Package Manager** | [uv](https://docs.astral.sh/uv/) (Python 3.12) |
| **Deployment** | Docker & Docker Compose |
| **Pixel Art Engine** | Script-generated SVG sprites & animated GIFs (`scripts/gen_sprites.py`) |

---

## 🚀 Quick Start (Local Development)

### Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

### 1. Install and Bootstrap
```bash
# Clone repository
git clone https://github.com/partrita/warant.git
cd warant

# Install dependencies with uv
uv sync

# Regenerate pixel-art sprites (optional)
uv run python scripts/gen_sprites.py

# Bootstrap Reflex frontend
uv run reflex init
```

### 2. Run Dev Server
```bash
uv run reflex run
```
Open [http://localhost:3000](http://localhost:3000) in your browser. (Backend API runs on `:8000`).

### 3. Run Unit Tests
```bash
uv run pytest
```

---

## 🐳 Production Deployment (Docker)

```bash
docker compose up --build -d
```
The game will be available at **http://localhost:8000**.
- Database persists in the `warant_data` named volume (`/data/warant.db`).
- Set `WARANT_SECRET` in your environment for secure session cookies.
- To switch to PostgreSQL, set `WARANT_DATABASE_URL=postgresql://user:pass@postgres:5432/warant`.

---

## 🎮 How to Play

1. **Found Your Nest** — Register with your queen's name; your nest is placed on an open world-map coordinate.
2. **Develop Infrastructure**:
   - 🍄 **Fungus Farm (버섯 농장)**: Produces Food.
   - 💧 **Dew Collector (이슬 수집기)**: Produces Water.
   - ☀️ **Sun Chamber (양광실)**: Accelerates Energy recovery.
   - 🌾 **Granary (저장고)**: Increases resource capacity.
   - 🏠 **Living Quarters (개미 숙소)**: Increases population cap.
3. **Research Technologies** — Upgrade Pheromone Communication, Mandible Hardening (턱 강화), Chitin Carapace, and Olfactory Tracking.
4. **Hatch Your Swarm** — Use the brood slider to hatch workers and specialized combatants.
5. **Scout & Hunt** — Send scout ants to gather intel on wilderness cells, then send strike teams to harvest wild insect bounties.
6. **Raid & Defend** — Scout rival nests, breach their gates, and plunder resources while fortifying your own tunnels.
7. **Join an Alliance** — Band together with fellow queens to conquer the leaderboard!

---

## 📁 Project Structure

```
warant/
├── rxconfig.py              # Reflex project configuration
├── pyproject.toml           # uv project & dependency definitions
├── Dockerfile               # Multi-stage production container
├── docker-compose.yml       # Docker compose setup
├── scripts/
│   └── gen_sprites.py       # Pixel-art SVG & GIF generator
├── tests/                   # Engine unit tests (pytest)
│   ├── test_engine.py
│   ├── test_ant_population.py
│   └── test_balance.py
└── warant/
    ├── warant.py            # App entry point, routes, background tick loop
    ├── gamedata.py          # Balance constants (buildings, units, tech, formulas)
    ├── models.py            # SQLModel database tables
    ├── engine.py            # Lazy simulation ticks, queues, marches, combat
    ├── db.py                # Database connection factory
    ├── auth_state.py        # Authentication & session management
    ├── components/
    │   └── layout.py        # Mobile-first shell (top bar, HUD, bottom nav)
    └── pages/               # Game pages
        ├── colony.py        # Nest overview & pixel animation
        ├── buildings.py     # Construction & queue management
        ├── brood.py         # Unit hatching with quantity slider
        ├── research.py      # Tech tree
        ├── map.py           # 100x100 world map, scouting & hunts
        ├── reports.py       # Combat & scout reports
        ├── alliance.py      # Alliance management & wars
        ├── ranking.py       # Player & alliance leaderboards
        └── more.py          # Settings, guides, profile
```

---

## 🤖 Agents

AI agents contributing to this codebase should review [`AGENTS.md`](AGENTS.md) before making changes.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
