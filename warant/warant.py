"""WarAnt app entry: pages, theme, and background game ticker."""

import asyncio
import contextlib

import reflex as rx
from . import db, engine
from .db import game_session
from .pages.alliance import alliance_page
from .pages.auth import index
from .pages.brood import brood_page
from .pages.buildings import buildings_page
from .pages.colony import colony_page
from .pages.map import map_page
from .pages.more import more_page
from .pages.ranking import ranking_page
from .pages.reports import reports_page
from .pages.research import research_page

db.init_db()


@contextlib.asynccontextmanager
async def _game_ticker():
    """Resolve due marches and ticks periodically, even when idle."""
    async def _loop():
        while True:
            try:
                with game_session() as s:
                    engine.process_all(s)
                    s.commit()
            except asyncio.CancelledError:
                break
            except Exception:  # noqa: BLE001 - keep the ticker alive no matter what
                pass
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break

    task = asyncio.create_task(_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = rx.App(
    head_components=[
        rx.el.link(
            rel="stylesheet",
            href="https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap",
        ),
    ],
)
app.register_lifespan_task(_game_ticker)

app.add_page(index, route="/", title="WarAnt — 여왕개미 전략")
app.add_page(colony_page, route="/colony", title="콜로니 | WarAnt")
app.add_page(buildings_page, route="/buildings", title="건설 | WarAnt")
app.add_page(brood_page, route="/brood", title="군세 | WarAnt")
app.add_page(map_page, route="/map", title="지도 | WarAnt")
app.add_page(more_page, route="/more", title="더보기 | WarAnt")
app.add_page(research_page, route="/more/research", title="연구 | WarAnt")
app.add_page(reports_page, route="/more/reports", title="보고서 | WarAnt")
app.add_page(alliance_page, route="/more/alliance", title="동맹 | WarAnt")
app.add_page(ranking_page, route="/more/ranking", title="랭킹 | WarAnt")
