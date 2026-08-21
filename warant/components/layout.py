"""Mobile-first game shell: resource bar, bottom navigation, shared widgets."""

from __future__ import annotations

import reflex as rx

from ..game_state import GameState

# Palette (soil / colony dark theme)
C_BG = "#171210"
C_PANEL = "#241c16"
C_PANEL_2 = "#2f251d"
C_BORDER = "#4a3a2c"
C_TEXT = "#e8dcc8"
C_DIM = "#9c8a72"
C_AMBER = "#e8a33d"
C_GREEN = "#8bc34a"
C_BLUE = "#5db8e8"
C_RED = "#e05d44"

MAX_W = "520px"
NAV_H = "64px"
TOP_H = "52px"

NAV_ITEMS = [
    ("/colony", "/img/icon_ant.svg", "콜로니"),
    ("/buildings", "/img/icon_hammer.svg", "건설"),
    ("/brood", "/img/icon_sword.svg", "군세"),
    ("/map", "/img/icon_map.svg", "지도"),
    ("/more", "/img/icon_menu.svg", "더보기"),
]


def pixel_img(src: str, size: int = 28) -> rx.Component:
    return rx.image(
        src=src,
        width=f"{size}px",
        height=f"{size}px",
        style={"image_rendering": "pixelated"},
        flex_shrink="0",
    )


def res_chip(icon: str, value: str, color: str, title: str = "") -> rx.Component:
    return rx.hstack(
        pixel_img(icon, 20),
        rx.text(value, color=color, size="2", weight="bold"),
        spacing="1",
        align="center",
        padding_x="6px",
        padding_y="3px",
        border_radius="8px",
        background=C_PANEL_2,
        border=f"1px solid {C_BORDER}",
        title=title,
    )


def energy_color(state: GameState) -> str:
    return C_GREEN if state.energy >= 20 else C_RED


def top_bar() -> rx.Component:
    return rx.hstack(
        rx.link(
            rx.hstack(
                pixel_img("/img/queen.svg", 26),
                rx.text("WarAnt", color=C_AMBER, weight="bold", size="3",
                        style={"font_family": "'Press Start 2P', monospace"}),
                spacing="1",
            ),
            href="/colony",
            text_decoration="none",
        ),
        rx.spacer(),
        rx.foreach(
            GameState.nests_list,
            lambda n: rx.cond(
                n[0] == GameState.nest_id,
                rx.button(n[1], " ", n[2].to(str), ":", n[3].to(str),
                          size="1", variant="surface", color_scheme="amber"),
                rx.button(
                    n[1], " ", n[2].to(str), ":", n[3].to(str),
                    size="1", variant="ghost",
                    color=C_DIM,
                    on_click=GameState.switch_nest(n[0].to(str)),
                ),
            ),
        ),
        width="100%",
        align="center",
        padding_x="10px",
        height=f"{TOP_H}px",
        position="sticky",
        top="0",
        background=C_BG,
        z_index="20",
        border_bottom=f"2px solid {C_BORDER}",
    )


def res_bar() -> rx.Component:
    return rx.hstack(
        rx.hstack(
            res_chip(
                "/img/res_food.svg",
                rx.cond(
                    GameState.food_rate_disp != "+0/h",
                    GameState.food_disp + " " + GameState.food_rate_disp,
                    GameState.food_disp,
                ),
                C_GREEN,
            ),
            res_chip("/img/res_water.svg", GameState.water_disp + " "
                     + GameState.water_rate_disp, C_BLUE),
        ),
        rx.spacer(),
        res_chip(
            "/img/res_energy.svg",
            GameState.energy_disp,
            C_AMBER,
            "행동 에너지 — 업그레이드·진군 등에 소모되며 시간이 지나면 회복됩니다",
        ),
        width="100%",
        align="center",
        padding_x="10px",
        padding_y="6px",
        position="sticky",
        top=f"{TOP_H}px",
        background=C_BG,
        z_index="19",
    )


def nav_button(route: str, icon: str, label: str, active_route: str) -> rx.Component:
    active = route == active_route
    return rx.link(
        rx.vstack(
            rx.image(
                src=icon,
                width="26px",
                height="26px",
                opacity="1" if active else "0.55",
                style={"image_rendering": "pixelated"},
            ),
            rx.text(
                label,
                size="1",
                weight="bold" if active else "medium",
                color=C_AMBER if active else C_DIM,
            ),
            spacing="1",
            align="center",
            justify_content="center",
            width="100%",
        ),
        href=route,
        flex="1",
        text_decoration="none",
        display="flex",
    )


def bottom_nav(active_route: str) -> rx.Component:
    return rx.hstack(
        *[nav_button(route, icon, label, active_route) for route, icon, label in NAV_ITEMS],
        width="100%",
        max_width=MAX_W,
        align="center",
        height=f"{NAV_H}px",
        padding="4px 6px",
        position="fixed",
        bottom="0",
        left="0",
        right="0",
        margin_x="auto",
        background=C_PANEL,
        border_top=f"2px solid {C_BORDER}",
        z_index="30",
    )


def toast_overlay() -> rx.Component:
    return rx.cond(
        GameState.toast != "",
        rx.center(
            rx.hstack(
                rx.text(GameState.toast, size="2", color=C_TEXT),
                rx.button("✕", size="1", variant="ghost", on_click=GameState.clear_toast,
                          color=C_DIM),
            ),
            position="fixed",
            top="92px",
            left="0",
            right="0",
            margin_x="auto",
            width="fit-content",
            max_width="90vw",
            background=C_PANEL_2,
            border=f"2px solid {C_AMBER}",
            border_radius="10px",
            padding="8px 14px",
            z_index="50",
        ),
    )


def progress_bar(pct, color: str = C_AMBER) -> rx.Component:
    width = rx.Var.create(pct).to(str) + "%"
    return rx.box(
        rx.box(
            width=width,
            height="100%",
            background=color,
            border_radius="4px",
        ),
        width="100%",
        height="10px",
        background="#120d0a",
        border=f"1px solid {C_BORDER}",
        border_radius="5px",
        overflow="hidden",
    )


def panel(*children, **props) -> rx.Component:
    spacing = props.pop("spacing", "3")
    return rx.vstack(
        *children,
        spacing=spacing,
        width="100%",
        background=C_PANEL,
        border=f"2px solid {C_BORDER}",
        border_radius="12px",
        padding="14px",
        **props,
    )


def page_title(text: str, icon: str = "") -> rx.Component:
    return rx.hstack(
        rx.cond(icon != "", pixel_img(icon, 24), rx.fragment()),
        rx.heading(text, size="5", color=C_TEXT),
        spacing="2",
        align="center",
        width="100%",
    )


def game_shell(active_route: str, *children, **props) -> rx.Component:
    """Standard mobile-first frame wrapping every game page."""
    page_mounts = props.pop("on_load", None) or []
    return rx.box(
        top_bar(),
        res_bar(),
        rx.vstack(
            *children,
            spacing="4",
            width="100%",
            max_width=MAX_W,
            margin_x="auto",
            padding="12px",
            padding_bottom="88px",
            align="stretch",
        ),
        bottom_nav(active_route),
        toast_overlay(),
        # periodic state refresh so resources & queues tick live
        rx.box(id="wa-refresh", display="none"),
        rx.button(
            "", id="wa-auto-refresh", display="none", on_click=GameState.refresh_game
        ),
        rx.script(
            "window.setInterval(function(){"
            "var b=document.getElementById('wa-auto-refresh');"
            "if(b) b.click();}, 15000);"
        ),
        min_height="100vh",
        background=C_BG,
        on_mount=[GameState.refresh_game] + list(page_mounts),
        **props,
    )
