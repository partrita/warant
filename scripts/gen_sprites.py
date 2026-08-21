"""Generate pixel-art SVG sprites for WarAnt into assets/img/.

Sprites are drawn on small pixel grids (12x12 or 16x16) and exported as
SVG rects with crisp edges, so they scale cleanly on any screen.

Usage:  uv run python scripts/gen_sprites.py
"""

from __future__ import annotations

import os

OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "img")


class Grid:
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.px: dict[tuple[int, int], str] = {}

    def set(self, x: int, y: int, c: str) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[(x, y)] = c

    def rect(self, x0: int, y0: int, x1: int, y1: int, c: str) -> None:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.set(x, y, c)

    def hline(self, y: int, x0: int, x1: int, c: str) -> None:
        for x in range(x0, x1 + 1):
            self.set(x, y, c)

    def vline(self, x: int, y0: int, y1: int, c: str) -> None:
        for y in range(y0, y1 + 1):
            self.set(x, y, c)

    def from_ascii(self, rows: list[str], palette: dict[str, str]) -> None:
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch != "." and ch in palette:
                    self.set(x, y, palette[ch])

    def to_svg(self) -> str:
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
            'shape-rendering="crispEdges">'
        ]
        # merge horizontal runs of the same color
        runs: list[tuple[int, int, int, str]] = []
        for y in range(self.h):
            x = 0
            while x < self.w:
                c = self.px.get((x, y))
                if c is None:
                    x += 1
                    continue
                x2 = x
                while x2 + 1 < self.w and self.px.get((x2 + 1, y)) == c:
                    x2 += 1
                runs.append((x, y, x2 - x + 1, c))
                x = x2 + 1
        for (x, y, w, c) in runs:
            parts.append(
                f'<rect x="{x}" y="{y}" width="{w}" height="1" fill="{c}"/>'
            )
        parts.append("</svg>")
        return "".join(parts)


# ---------------------------------------------------------------------------
# Parametrized ant drawer (side view, facing right)
# ---------------------------------------------------------------------------


def draw_ant(
    gr: Grid,
    ox: int,
    oy: int,
    body: str,
    dark: str,
    eye_c: str,
    jaw: str | None = None,
    wings: bool = False,
    wing_c: str = "#cfe3f5",
    acid: bool = False,
    big: bool = False,
) -> None:
    """Draw a little ant. Origin is the top-left of its bounding box."""
    # abdomen (left)
    gr.rect(ox, oy + 4, ox + 3, oy + 7, body)
    gr.set(ox, oy + 3, body)
    gr.set(ox + 1, oy + 8, body)
    # abdomen shading
    gr.set(ox, oy + 6, dark)
    gr.set(ox + 1, oy + 7, dark)

    # petiole
    gr.set(ox + 4, oy + 5, body)

    # thorax
    gr.rect(ox + 5, oy + 4, ox + 7, oy + 6, body)

    # head
    gr.rect(ox + 8, oy + 3, ox + 10, oy + 5, body)
    gr.set(ox + 10, oy + 5, dark)
    gr.set(ox + 9, oy + 4, eye_c)

    # mandibles / jaws
    if jaw == "big":
        gr.set(ox + 11, oy + 4, dark)
        gr.set(ox + 12, oy + 3, dark)
        gr.set(ox + 12, oy + 6, dark)
    else:
        gr.set(ox + 11, oy + 4, dark)
        gr.set(ox + 12, oy + 5, dark)

    # antennae
    gr.set(ox + 10, oy + 2, dark)
    gr.set(ox + 11, oy + 1, dark)

    # legs (three pairs)
    gr.set(ox + 5, oy + 7, dark)
    gr.set(ox + 4, oy + 8, dark)
    gr.set(ox + 6, oy + 7, dark)
    gr.set(ox + 6, oy + 8, dark)
    gr.set(ox + 7, oy + 7, dark)
    gr.set(ox + 8, oy + 8, dark)

    if wings:
        gr.set(ox + 5, oy + 2, wing_c)
        gr.set(ox + 6, oy + 1, wing_c)
        gr.set(ox + 7, oy + 2, wing_c)
        gr.set(ox + 8, oy + 1, wing_c)
        gr.set(ox + 6, oy + 3, wing_c)

    if acid:
        gr.set(ox + 12, oy + 2, "#9ede4a")
        gr.set(ox + 13, oy + 1, "#b6f05e")


def ant_sprite(body: str, dark: str, **kw) -> Grid:
    g = Grid(16, 16)
    draw_ant(g, 1, 4, body, dark, "#111111", **kw)
    return g


# ---------------------------------------------------------------------------
# Resource icons
# ---------------------------------------------------------------------------


def res_food_grid() -> Grid:
    g = Grid(12, 12)
    pal = {
        "g": "#5e9c34", "G": "#7cbf42", "r": "#c93a2e",
        "R": "#e86a52", "d": "#8f2318", "h": "#f2a58c",
    }
    g.from_ascii(
        [
            "............",
            ".....GG.....",
            "....GG.g....",
            "...rrrr.....",
            "..rRrrrd....",
            ".rhRrrrrd...",
            ".rRRrrrrd...",
            ".rrrrrrdd...",
            "..rrrrdd....",
            "...rrdd.....",
            "............",
            "............",
        ],
        pal,
    )
    return g


def res_water_grid() -> Grid:
    g = Grid(12, 12)
    pal = {
        "b": "#3f97d6", "B": "#79c7ef", "w": "#d8f2fc",
        "d": "#25688f",
    }
    g.from_ascii(
        [
            "............",
            ".....ww.....",
            ".....BB.....",
            "....BBBB....",
            "....BBBB....",
            "...BBBBBB...",
            "..bBBBBBBb..",
            "..bBBwBBBb..",
            ".bbBBBBBBdb.",
            ".bbBBBBBBdb.",
            "..bbBBBBdb..",
            "....bbbb....",
        ],
        pal,
    )
    return g


def res_energy_grid() -> Grid:
    g = Grid(12, 12)
    pal = {
        "y": "#e8a33d", "Y": "#ffd166", "o": "#b56a17", "w": "#fff3d6",
    }
    g.from_ascii(
        [
            "............",
            "......yy....",
            ".....yYYo...",
            "....yYwYYo..",
            "...yYYwYYYo.",
            "..yyyYYyyyy.",
            "...ooYYyoo..",
            "....oyYyo...",
            ".....oyo....",
            ".....oo.....",
            "......o.....",
            "............",
        ],
        pal,
    )
    return g


# ---------------------------------------------------------------------------
# Nav / action icons
# ---------------------------------------------------------------------------


def icon_ant_grid() -> Grid:
    return ant_sprite("#b3542e", "#7a3018")


def icon_hammer_grid() -> Grid:
    g = Grid(12, 12)
    pal = {"s": "#9aa3ad", "S": "#cfd6dd", "h": "#8a5a2b", "H": "#b5793c"}
    g.from_ascii(
        [
            "............",
            "....SSSS....",
            "...SSSSSSS..",
            "...SSSSSSS..",
            "....SSSS.h..",
            ".......hH...",
            "......hH....",
            ".....hH.....",
            "....hH......",
            "...hH.......",
            "..hH........",
            "..h.........",
        ],
        pal,
    )
    return g


def icon_sword_grid() -> Grid:
    g = Grid(12, 12)
    pal = {"s": "#c9d4de", "S": "#f2f7fb", "h": "#8a5a2b", "g": "#e8a33d"}
    g.from_ascii(
        [
            ".........SS.",
            "........sS..",
            ".......ss...",
            "......ss....",
            ".....ss.....",
            "..g.ss......",
            "...gs.......",
            "..hgg.......",
            ".hh..g......",
            "hh..........",
            "............",
            "............",
        ],
        pal,
    )
    return g


def icon_map_grid() -> Grid:
    g = Grid(12, 12)
    pal = {"p": "#d8c69a", "P": "#efe2bd", "l": "#7cbf42", "b": "#3f97d6", "r": "#c93a2e"}
    g.from_ascii(
        [
            "............",
            ".PPP...PPP..",
            "PPpP...PpPP.",
            "PPlPPlllPP.P",
            "PPPPPPPrPPP.",
            "P.b.PPPPPPP.",
            ".bb..PPPP...",
            "..b..PP.....",
            ".....P......",
            "............",
            "............",
            "............",
        ],
        pal,
    )
    return g


def icon_menu_grid() -> Grid:
    g = Grid(12, 12)
    for i, y in enumerate([2, 5, 8]):
        g.hline(y, 1, 10, "#c9b48a")
        g.hline(y + 1, 1, 10, "#8a7554")
    return g


def icon_attack_grid() -> Grid:
    g = Grid(12, 12)
    pal = {"r": "#c93a2e", "R": "#e86a52", "w": "#f2f7fb"}
    g.from_ascii(
        [
            ".....R......",
            "....RRR.....",
            "...RRRRR....",
            ".RR.RrR.RR..",
            "..RRRrRRR...",
            "....RrR.....",
            "...RrrrR....",
            "...RrrrR....",
            "....RrR.....",
            "...R...R....",
            "..R.....R...",
            "............",
        ],
        pal,
    )
    return g


def icon_scout_grid() -> Grid:
    g = Grid(12, 12)
    pal = {"w": "#f2f7fb", "b": "#3f97d6", "k": "#171210", "W": "#cfd6dd"}
    g.from_ascii(
        [
            "............",
            "............",
            "...WWWWWW...",
            ".WWWbbbbWW..",
            "WbbbbkbkbWW.",
            "WbbbkkkkbWW.",
            ".WWbbbbkWW..",
            "...WWWWWW...",
            "............",
            "............",
            "............",
            "............",
        ],
        pal,
    )
    return g


def icon_hunt_grid() -> Grid:
    g = Grid(12, 12)
    pal = {"r": "#c93a2e", "R": "#e86a52", "w": "#f2f7fb", "g": "#5e9c34"}
    g.from_ascii(
        [
            "....gg......",
            "...g..g.....",
            "..g.gg.g....",
            ".g..RR..g...",
            "...RrrR.....",
            "..RrwrrR....",
            "..RrrrrR....",
            "...RrrR.....",
            "..g.RR.g....",
            ".g..gg..g...",
            "...g..g.....",
            "....gg......",
        ],
        pal,
    )
    return g


def icon_transfer_grid() -> Grid:
    g = Grid(12, 12)
    pal = {"g": "#8bc34a", "G": "#aed659", "b": "#3f97d6", "B": "#79c7ef"}
    g.from_ascii(
        [
            "............",
            "...G.....b..",
            "..GG.GG..bb.",
            ".GGG.GGG.bbb",
            "..GG.GG..bb.",
            "...G.....b..",
            "............",
            "..b.....G...",
            ".bbb.GGG.GG.",
            "..bb.GG..GG.",
            "...b.....G..",
            "............",
        ],
        pal,
    )
    return g


def icon_report_grid() -> Grid:
    g = Grid(12, 12)
    pal = {"p": "#efe2bd", "P": "#d8c69a", "l": "#6b5a41", "r": "#c93a2e"}
    g.from_ascii(
        [
            "...PPPPPP...",
            "..PppppppP..",
            "..PplplppP..",
            "..PppppppP..",
            "..PplplprpP.",
            "..PppppprpP.",
            "..PplplppP..",
            "..PppppppP..",
            "..PplplppP..",
            "..PppppppP..",
            "...PPPPPP...",
            "............",
        ],
        pal,
    )
    return g


def icon_trophy_grid() -> Grid:
    g = Grid(12, 12)
    pal = {"y": "#e8a33d", "Y": "#ffd166", "o": "#b56a17", "h": "#8a5a2b"}
    g.from_ascii(
        [
            ".YYYYYYYYY..",
            ".YYYYYYYYYo.",
            "YyYYYYYYYyo.",
            "YyYYYYYYyo..",
            ".oyYYYYyo...",
            "..oYYYYo....",
            "...oYYo.....",
            "....YY......",
            "....hh......",
            "...hhhh.....",
            "..hhhhhh....",
            "............",
        ],
        pal,
    )
    return g


def icon_flag_grid() -> Grid:
    g = Grid(12, 12)
    pal = {"r": "#c93a2e", "R": "#e86a52", "h": "#8a5a2b", "H": "#b5793c"}
    g.from_ascii(
        [
            ".hh.........",
            ".hhRRRRRR...",
            ".hhRRRRRRR..",
            ".hhRRRRRR...",
            ".hhRRRR.....",
            ".hhRRRRRR...",
            ".hhRRRRRRR..",
            ".hhRRRRRR...",
            ".hh.........",
            ".hh.........",
            ".hh.........",
            "............",
        ],
        pal,
    )
    return g


def icon_shield_grid() -> Grid:
    g = Grid(12, 12)
    pal = {"s": "#8a97a5", "S": "#c9d4de", "d": "#5c6873", "g": "#e8a33d"}
    g.from_ascii(
        [
            ".SSSSSSSS...",
            ".SsssssssS..",
            ".SsggggssS..",
            ".Ssgssgsss..",
            ".Ssgssgsss..",
            ".Sssggssss..",
            "..Ssgssssd..",
            "..Ssssssd...",
            "...Ssssd....",
            "....Sdd.....",
            ".....S......",
            "............",
        ],
        pal,
    )
    return g


def queen_grid() -> Grid:
    """Colony logo: crowned queen ant facing right."""
    g = Grid(16, 16)
    pal = {"y": "#ffd166", "o": "#e8a33d", "b": "#a03e22", "B": "#c95a33",
           "d": "#6e2512", "e": "#111111", "j": "#6e2512"}
    # crown
    g.from_ascii(
        [
            "..........o.o.",
            ".........oyoyo",
            ".........ooooo",
            "..........ooo.",
        ],
        pal,
    )
    draw_queen_body(g, pal)
    return g


def draw_queen_body(g: Grid, pal: dict) -> None:
    b, B, d = pal["b"], pal["B"], pal["d"]
    # large abdomen
    g.rect(0, 7, 5, 13, B)
    g.rect(0, 8, 4, 12, b)
    g.set(1, 9, d)
    g.set(2, 11, d)
    g.set(1, 12, d)
    # petiole + thorax
    g.set(6, 9, B)
    g.rect(7, 8, 9, 11, b)
    # head
    g.rect(10, 7, 12, 10, B)
    g.set(12, 9, d)
    g.set(11, 8, "#111111")
    # jaws
    g.set(13, 8, d)
    g.set(14, 9, d)
    # antennae
    g.set(12, 6, d)
    g.set(13, 5, d)
    # legs
    for x, y in [(7, 12), (6, 13), (9, 12), (9, 13), (8, 12)]:
        g.set(x, y, d)


# ---------------------------------------------------------------------------
# Buildings (16x16)
# ---------------------------------------------------------------------------


def bld_fungus_farm() -> Grid:
    g = Grid(16, 16)
    pal = {
        "m": "#b98a5a", "M": "#d9b48a", "t": "#8a6a44", "c": "#efe2bd",
        "C": "#fdf6df", "s": "#6b4e2e", "g": "#7cbf42",
    }
    rows = [
        "................",
        "................",
        "....CC..CC......",
        "...cCCccCCc.....",
        "..cccccccccc.c..",
        "..CCCCCCCCcccC..",
        ".mmmmmmmmmmmCc..",
        ".mtttttttttmm...",
        ".mttttttttttm...",
        "mmttttttttttmm..",
        "mttttttttttttm..",
        "mttssttttssttm..",
        "mttssttttssttm..",
        "mmmmmmmmmmmmmm..",
        "................",
        "................",
    ]
    g.from_ascii(rows, pal)
    return g


def bld_dew_collector() -> Grid:
    g = Grid(16, 16)
    pal = {
        "w": "#79c7ef", "W": "#d8f2fc", "b": "#3f97d6", "t": "#8a6a44",
        "T": "#b98a5a", "s": "#6b4e2e",
    }
    rows = [
        "................",
        "......TTTT......",
        ".....T....T.....",
        "....T......T....",
        "....T..WW..T....",
        ".....T.WW.T.....",
        ".....T.WW.T.....",
        "......TWWT......",
        ".......bb.......",
        ".......bb.......",
        "......sbb.s.....",
        ".....ssbbss.....",
        "....TTTTTTTT....",
        "...TTTTTTTTTT...",
        "................",
        "................",
    ]
    g.from_ascii(rows, pal)
    return g


def bld_sun_chamber() -> Grid:
    g = Grid(16, 16)
    pal = {
        "y": "#ffd166", "Y": "#ffe9a8", "o": "#e8a33d", "t": "#8a6a44",
        "T": "#b98a5a", "O": "#b56a17",
    }
    rows = [
        "................",
        "......YYYY......",
        "....YYYYYYYY....",
        "...YYooYYooYY...",
        "...YoooooooooY..",
        "..YYoYYooYYoYY..",
        "..YooooooooooY..",
        "..YYoYYooYYoYY..",
        "...YoooooooooY..",
        "....YYoooYYY....",
        ".....YYYYY......",
        "....TTTTTTT.....",
        "...TTTTTTTTT....",
        "..TTTTTTTTTTT...",
        "................",
        "................",
    ]
    g.from_ascii(rows, pal)
    return g


def bld_granary() -> Grid:
    g = Grid(16, 16)
    pal = {
        "m": "#b98a5a", "M": "#d9b48a", "s": "#6b4e2e", "S": "#4a3620",
        "y": "#e8c46a", "t": "#8a6a44",
    }
    rows = [
        "................",
        "......MM........",
        "....MMMMMM......",
        "...MMmmmmMM.....",
        "..MMmyymymMM....",
        ".MMmmyymymmMM...",
        ".MmmmmmmmmmmM...",
        ".Mmsmmmmmsm mM..".replace(" ", "m"),
        "Mmmmsmmmmsmmmm..",
        "Mmmmmmmmmmmmm...",
        "Mmmsmmmmmsmmm...",
        "Mmmmmmmmmmmmm...",
        "MMMMMMMMMMMMM...",
        ".SSSSSSSSSSS....",
        "................",
        "................",
    ]
    g.from_ascii(rows, pal)
    return g


def bld_brood_chamber() -> Grid:
    g = Grid(16, 16)
    pal = {
        "m": "#b98a5a", "M": "#d9b48a", "t": "#8a6a44", "e": "#fdf6df",
        "E": "#efe2bd", "w": "#f7ecd0",
    }
    rows = [
        "................",
        "................",
        "...MMMMMMMM.....",
        "..Meeeeeeem M...".replace(" ", ""),
        ".MEeeEEeeeemM...",
        ".MEweEEewEeem...",
        ".MEEEEEEEEEem...",
        ".MEeeEEeeeemm...",
        ".MEEEEEEEEEmm...",
        "mmmmmmmmmmmmmm..",
        "mttttttttttttm..",
        "mttetttetttetm..",
        "mttttttttttttm..",
        "mmmmmmmmmmmmmm..",
        "................",
        "................",
    ]
    g.from_ascii(rows, pal)
    return g


def bld_research_chamber() -> Grid:
    g = Grid(16, 16)
    pal = {
        "m": "#b98a5a", "M": "#d9b48a", "t": "#8a6a44", "p": "#efe2bd",
        "P": "#fdf6df", "b": "#3f97d6", "s": "#6b4e2e",
    }
    rows = [
        "................",
        "....PPPP........",
        "...PpppppP......",
        "...PpbpbpPP.....",
        "...PpppppbP.....",
        "...PpbpbppP....",
        "...PpppppP......",
        "..MMMPPPPMM.....",
        ".MmmmmmmmmmM....",
        ".MmtttttttmM....",
        "MmmmmmmmmmmmM...",
        "Mmtsstsststmm...",
        "MmmmmmmmmmmmM...",
        "MMMMMMMMMMMMM...",
        "................",
        "................",
    ]
    g.from_ascii(rows, pal)
    return g


def bld_tunnel_network() -> Grid:
    g = Grid(16, 16)
    pal = {"d": "#6b4e2e", "D": "#4a3620", "m": "#8a6a44", "k": "#241a10"}
    rows = [
        "................",
        "................",
        "mmDDmmmmDDmmmm..",
        "mDkkDmmDkkDmmm..",
        "mDkkDmmDkkDmmm..",
        "mmDDmmmmDDmmmm..",
        "mmmmmDDmmmmmmm..",
        "mmmmDkkDmmmmmm..",
        "mmmmDkkDmmmmmm..",
        "mmmmmDDmmmmmmm..",
        "mmDDmmmmDDmmmm..",
        "mDkkDmmDkkDmmm..",
        "mDkkDmmDkkDmmm..",
        "mmDDmmmmDDmmmm..",
        "................",
        "................",
    ]
    g.from_ascii(rows, pal)
    return g


def bld_thorn_gate() -> Grid:
    g = Grid(16, 16)
    pal = {"t": "#8a6a44", "T": "#b98a5a", "s": "#6b4e2e", "S": "#d9c9a8",
           "g": "#5e9c34", "G": "#7cbf42"}
    rows = [
        "................",
        "..G...G...G.....",
        "..gG..gG..gG....",
        "..TgT.TgT.TgT...",
        ".TTgTTTgTTTgTT..",
        ".TTTTTTTTTTTTT..",
        ".TSSTTTTSSTTTT..",
        ".TSSTTTTSSTTTT..",
        ".TTTTTTTTTTTTT..",
        ".TTSSTTTTSSTT...",
        ".TTSSTTTTSSTT...",
        ".TTTTTTTTTTTTT..",
        "................",
        "................",
        "................",
        "................",
    ]
    g.from_ascii(rows, pal)
    return g


def bld_watch_post() -> Grid:
    g = Grid(16, 16)
    pal = {"t": "#8a6a44", "T": "#b98a5a", "s": "#6b4e2e", "e": "#ffd166",
           "E": "#fff3d6"}
    rows = [
        "......TEET......",
        "......TEET......",
        ".......ee.......",
        ".....TTTTTT.....",
        "....TtTTTTtT....",
        "......TTTT......",
        "......TttT......",
        "......TttT......",
        "......TttT......",
        ".....TTttTT.....",
        ".....TTttTT.....",
        "....TTTttTTT....",
        "....TTTTTTTT....",
        "..TTTTTTTTTTTT..",
        "................",
        "................",
    ]
    g.from_ascii(rows, pal)
    return g


# ---------------------------------------------------------------------------
# Wild insects (12x12)
# ---------------------------------------------------------------------------


def wild_beetle() -> Grid:
    g = Grid(12, 12)
    pal = {"g": "#3e6b21", "G": "#5e9c34", "d": "#26420f", "l": "#8bc34a",
           "k": "#141c08"}
    rows = [
        "............",
        "............",
        "....dddddd..",
        "..ddGGGGGgd.",
        ".dGlGdGGGggd",
        ".dGGdGdGGggd",
        ".dGdGGdGGggd",
        ".dGGdGdGGggd",
        "..dGGGGGggd.",
        "...ddddddd..",
        "..k.k...k.k.",
        "............",
    ]
    g.from_ascii(rows, pal)
    return g


def wild_spider() -> Grid:
    g = Grid(12, 12)
    pal = {"k": "#2b2430", "K": "#453a52", "e": "#e05d44", "w": "#6b5a80"}
    rows = [
        "............",
        "k..k...k..k.",
        ".k.k...k.k..",
        ".wk.kwk.kw..",
        "..kKKKKkw...",
        ".wKKKKKKk...",
        "..KeKeKkk...",
        ".wkKKKKk....",
        ".k.kkkk.k...",
        "k...k...k..k",
        "............",
        "............",
    ]
    g.from_ascii(rows, pal)
    return g


def wild_wasp() -> Grid:
    g = Grid(12, 12)
    pal = {"y": "#ffd166", "Y": "#fff3d6", "k": "#241a10", "w": "#cfe3f5",
           "b": "#3f97d6"}
    rows = [
        "............",
        "..w..w......",
        "...www......",
        "....kykyk...",
        "...wkyykw...",
        "..kyykyyk...",
        "..kykyykk...",
        "...kyyk.....",
        "....kk......",
        "...k..k.....",
        "............",
        "............",
    ]
    g.from_ascii(rows, pal)
    return g


def wild_mantis() -> Grid:
    g = Grid(12, 12)
    pal = {"g": "#5e9c34", "G": "#7cbf42", "L": "#a3d160", "e": "#e8a33d",
           "d": "#3e6b21"}
    rows = [
        "............",
        ".....LL.....",
        "....LGGL....",
        "....LeGL....",
        "..d.LGGL....",
        ".dGLLLLGGd..",
        "dGGLLLLLGGd.",
        "..dGLLLGd...",
        "...GLLG.....",
        "..d.LG.d....",
        ".d..LG......",
        "....d.......",
    ]
    g.from_ascii(rows, pal)
    return g


# ---------------------------------------------------------------------------
# Unit sprites via parametrized ant
# ---------------------------------------------------------------------------


def unit_worker():
    return ant_sprite("#b3703c", "#7a4a24")


def unit_soldier():
    return ant_sprite("#b3542e", "#7a3018", jaw="big")


def unit_scout():
    return ant_sprite("#c9a06a", "#8a6438")


def unit_flyer():
    return ant_sprite("#8a6aa5", "#5c4370", wings=True)


def unit_major():
    return ant_sprite("#8f2f22", "#5c1c14", jaw="big", big=True)


def unit_trap_jaw():
    return ant_sprite("#4a3620", "#241a10", jaw="big")


def unit_acid_ant():
    return ant_sprite("#5a7d2e", "#39521c", acid=True)


def def_pit_trap():
    g = Grid(12, 12)
    pal = {"d": "#6b4e2e", "k": "#241a10", "b": "#8a6a44", "B": "#b98a5a"}
    rows = [
        "............",
        "............",
        "..bbbbbbbb..",
        ".b.k.k.k.k.b",
        ".bk.k.k.k.kb",
        ".bbbbbbbbbbb",
        ".bkkkkkkkkkb",
        ".bk.k.k.k.kb",
        ".bkkkkkkkkkb",
        "..bbbbbbbbb.",
        "............",
        "............",
    ]
    g.from_ascii(rows, pal)
    return g


def def_thorn_pit():
    g = Grid(12, 12)
    pal = {"d": "#6b4e2e", "k": "#241a10", "s": "#d9c9a8", "S": "#efe2bd"}
    rows = [
        "............",
        "..s..s..s...",
        "..Ss.Ss.Ss..",
        ".dsdsdsdsds.",
        ".dkkkkkkkkd.",
        ".dkkkkkkkkd.",
        "ddkkkkkkkkdd",
        "dkkkkkkkkkkd",
        "ddkkkkkkkkdd",
        ".dddddddddd.",
        "............",
        "............",
    ]
    g.from_ascii(rows, pal)
    return g


def def_acid_sprayer():
    g = Grid(12, 12)
    pal = {"g": "#5e9c34", "G": "#9ede4a", "d": "#39521c", "k": "#241a10",
           "b": "#8a6a44"}
    rows = [
        "............",
        ".........GG.",
        "........GGg.",
        "......bbkg..",
        ".....bbk....",
        "....bbk.....",
        "...ggk......",
        "..gggg......",
        ".ggggg......",
        "..ggg.......",
        "............",
        "............",
    ]
    g.from_ascii(rows, pal)
    return g


# ---------------------------------------------------------------------------
# Export all
# ---------------------------------------------------------------------------

SPRITES: dict[str, callable] = {
    "queen": queen_grid,
    "icon_ant": icon_ant_grid,
    "icon_hammer": icon_hammer_grid,
    "icon_sword": icon_sword_grid,
    "icon_map": icon_map_grid,
    "icon_menu": icon_menu_grid,
    "res_food": res_food_grid,
    "res_water": res_water_grid,
    "res_energy": res_energy_grid,
    "icon_attack": icon_attack_grid,
    "icon_scout": icon_scout_grid,
    "icon_hunt": icon_hunt_grid,
    "icon_transfer": icon_transfer_grid,
    "icon_report": icon_report_grid,
    "icon_trophy": icon_trophy_grid,
    "icon_flag": icon_flag_grid,
    "icon_shield": icon_shield_grid,
    "b_fungus_farm": bld_fungus_farm,
    "b_dew_collector": bld_dew_collector,
    "b_sun_chamber": bld_sun_chamber,
    "b_granary": bld_granary,
    "b_brood_chamber": bld_brood_chamber,
    "b_research_chamber": bld_research_chamber,
    "b_tunnel_network": bld_tunnel_network,
    "b_thorn_gate": bld_thorn_gate,
    "b_watch_post": bld_watch_post,
    "u_worker": unit_worker,
    "u_soldier": unit_soldier,
    "u_scout": unit_scout,
    "u_flyer": unit_flyer,
    "u_major": unit_major,
    "u_trap_jaw": unit_trap_jaw,
    "u_acid_ant": unit_acid_ant,
    "u_pit_trap": def_pit_trap,
    "u_thorn_pit": def_thorn_pit,
    "u_acid_sprayer": def_acid_sprayer,
    "w_beetle": wild_beetle,
    "w_spider": wild_spider,
    "w_wasp": wild_wasp,
    "w_mantis": wild_mantis,
}


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    for name, fn in SPRITES.items():
        svg = fn().to_svg()
        path = os.path.join(OUT, f"{name}.svg")
        with open(path, "w") as f:
            f.write(svg)
    print(f"wrote {len(SPRITES)} sprites to {os.path.abspath(OUT)}")


if __name__ == "__main__":
    main()
