# WarAnt 👑🐜

**WarAnt** is a multiplayer browser strategy game where you play as an **ant queen**, inspired by OGame. Build your colony, forage and hunt in the wilderness, raid rival nests, and grow your empire alongside — and against — other players through **alliances and wars**.

[한국어 README](README.ko.md)

## Features

- **Real-time colony economy** — food and water accumulate over time (OGame-style), capped by granary storage.
- **Action energy** — upgrades, research, and marches cost energy (max 100) that refills over time.
- **Realistic build times** — early upgrades take seconds; high levels take hours or days.
- **Brood chamber** — hatch workers, soldiers, scouts, flyers, majors, trap-jaws, and acid ants.
- **World map (100×100)** — attack, scout, hunt wild insects, transfer resources, or garrison between your nests.
- **Combat** — round-based battles with unit stats, research bonuses, thorn-gate defense, tunnel-network loot hiding, and newbie protection.
- **Alliances & wars** — found alliances and declare 72-hour wars with kill-point scoring (+25% attack power during war).
- **Rankings** — compete by colony points across players and alliances.
- **Pixel-art UI** — hand-crafted pixel sprites, mobile-first design with bottom navigation.

## Tech stack

| Layer      | Choice                                        |
| ---------- | --------------------------------------------- |
| Full-stack | [Reflex](https://reflex.dev) (Python → React) |
| Database   | SQLModel / SQLAlchemy (SQLite default, PostgreSQL optional) |
| Deps       | [uv](https://docs.astral.sh/uv/)              |
| Deploy     | Docker / docker compose                       |
| Assets     | Generated pixel-art SVGs (`scripts/gen_sprites.py`) |

## Quick start (local dev)

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                      # install dependencies
uv run python scripts/gen_sprites.py   # regenerate pixel art into assets/img/
uv run reflex init           # one-time frontend bootstrap
uv run reflex run            # dev server at http://localhost:3000
```

Run tests:

```bash
uv run pytest
```

## Deploy with Docker

```bash
docker compose up --build
```

The game listens on **http://localhost:8000**. Data persists in the `warant_data` volume (`/data/warant.db`). Set `WARANT_SECRET` for session-token signing, and optionally switch to PostgreSQL by pointing `WARANT_DATABASE_URL` at a `postgres` service (see `docker-compose.yml`).

## How to play

1. **Register** — pick a queen name; your first nest is founded on a free map cell.
2. **Grow** — upgrade the fungus farm (food), dew collector (water), sun chamber (energy regen), and granary (storage).
3. **Hatch ants** — the brood chamber turns resources into units over real time.
4. **Scout & hunt** — send scouts to spy on neighbors; send workers/soldiers to wilderness cells to hunt insects for bonus food and water (watch out — deeper wilderness is more dangerous).
5. **Raid** — attack enemy nests to steal stored resources (tunnel networks hide some of it).
6. **Ally** — join or found an alliance; leaders can declare wars worth kill points.
7. **Climb the rankings** — every building level, unit, and tech contributes colony points.

### Resources

| Icon | Resource | Purpose |
| ---- | -------- | ------- |
| 🍒 | **Food** | Buildings, units, research |
| 💧 | **Water** | Buildings, units, research |
| ⚡ | **Energy** | Action currency — costs energy to upgrade/build/march; refills over time (sun chamber speeds this up) |

## Project structure

```
warant/
├── rxconfig.py            # Reflex config
├── pyproject.toml         # uv-managed dependencies
├── Dockerfile             # production image (frontend pre-built)
├── docker-compose.yml
├── scripts/gen_sprites.py # pixel-art SVG generator -> assets/img/
├── tests/                 # engine unit tests (pytest)
└── warant/
    ├── warant.py          # app wiring, routes, background ticker
    ├── gamedata.py        # balance: buildings, units, research, formulas
    ├── models.py          # SQLModel tables
    ├── engine.py          # resource ticks, queues, marches, combat
    ├── db.py              # engine/session factory (SQLite/Postgres)
    ├── auth_state.py      # register/login/logout (bcrypt + signed cookie)
    ├── components/layout.py  # mobile-first shell (top bar, bottom nav)
    └── pages/             # colony, buildings, brood, research, map,
                           # reports, alliance, ranking, more
```

## Agents

AI agents working on this repository should read [`AGENTS.md`](AGENTS.md) first.

---

MIT License — see [LICENSE](LICENSE).
