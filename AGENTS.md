<!-- reflex managed begin (do not edit inside this block; add custom content outside the markers) -->
# Agents

This project uses the **Reflex agent skills** — up-to-date knowledge for building full-stack Python web apps with [Reflex](https://reflex.dev). Install them first, then use them as described below.

## Installing the Skills

Before working on this project, make sure the Reflex skills are available to you.

### Claude Code

If the skills are not already available, install them yourself by running these shell commands:

```bash
claude plugin marketplace add reflex-dev/agent-skills
claude plugin install reflex@reflex-agent-skills
```

Newly installed plugins load on the next session. After installing, tell the user to restart the session so the skills auto-load; until then, read the skill files directly from `~/.claude/plugins/` when you need them.

### Other agents (Cursor, OpenCode, Codex, Pi)

```
npx skills add reflex-dev/agent-skills
```

Or clone https://github.com/reflex-dev/agent-skills and copy the `skills/` folders into your agent's skill directory (see the repo README for paths).

### Verifying

Before writing or editing any Reflex code, confirm these three skills are available: `reflex-docs`, `setup-python-env`, and `reflex-process-management`. If they are not, STOP and run the install step above — do not proceed without them.

## Using the Skills

### Reflex documentation

For anything about Reflex APIs — components, state management, events, styling, database, routing, authentication — use the **reflex-docs** skill rather than relying on memory. It carries current, version-accurate docs.

### Initializing a new Reflex project

When starting a new Reflex project or setting up a development environment, you **must** follow the **setup-python-env** skill before doing anything else.

Do not skip any steps. Do not assume a virtual environment or Reflex is already available — always verify first by following the skill's instructions in order.

After the environment is ready and Reflex is installed, run:

```bash
reflex init
```

Then proceed with the user's request.

### Managing a Reflex process

When you need to compile, run, reload, or debug a Reflex application, follow the **reflex-process-management** skill for the correct sequence and error investigation steps.
<!-- reflex managed end -->

# Luna Chat Coder entry point

When repository development is requested from a chat surface with a disposable or sandboxed code-execution environment, read `.agents/skills/luna-chat-coder/SKILL.md` before working on the repository task.

Loading the skill is a readiness step, not a reason to use GitHub Actions. Normal engineering work should stay in the chat sandbox work container when it is available and sufficient.

The repository itself defines its runtimes, services, dependencies, architecture, build system, and verification requirements. Luna Chat Coder supplies continuity and missing execution capability; it does not introduce a development methodology or substitute technologies merely because they are easier to run.

Treat exact GitHub commit and PR state as durable source truth, preserve unrelated work, and do not make access to the user's computer a dependency of the workflow.

When this repository is used as a template, keep this entry point and add the project's own engineering instructions alongside it.

# WarAnt engineering notes

WarAnt is a multiplayer ant-queen colony strategy game (OGame-inspired) built with Reflex, managed by uv, deployed with Docker. See [README.ko.md](README.ko.md) for the full game/design doc.

## Commands

```bash
uv sync                                # install deps (Python 3.12)
uv run pytest                          # run engine unit tests
uv run python scripts/gen_sprites.py   # regenerate pixel-art SVGs into assets/img/
uv run reflex init                     # one-time frontend bootstrap
uv run reflex run                      # dev server on :3000 (backend :8000)
docker compose up --build              # production-style run on :8000
```

## Architecture

- `warant/gamedata.py` — single source of balance truth (buildings, units, research, energy costs, formulas). Never hardcode numbers in pages.
- `warant/models.py` — SQLModel tables. All datetimes are naive UTC (`gamedata.utc_now`).
- `warant/engine.py` — lazy OGame-style simulation: `process_player` fast-forwards resources/queues; `process_due_marches` resolves attacks/scouts/hunts/transfers; `battle_rounds` simulates combat.
- Energy is an **action resource** (max 100, refills over time, spent by upgrades/marches) — not a produced resource. Use `engine.consume_energy`.
- States subclass `GameState` (which subclasses `AuthState`); every page calls its loader via `on_load`, plus a global 15s auto-refresh wired in `components/layout.py:game_shell`.
- Pixel sprites are generated code — edit `scripts/gen_sprites.py`, never hand-edit `assets/img/*.svg`.

## Verification before completing changes

1. `uv run pytest` must pass.
2. `uv run python -c "import warant.warant"` must succeed.
3. Run the app and smoke-test affected routes (HTTP 200 + no `ReflexError` in logs).
