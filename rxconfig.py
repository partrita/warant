import reflex as rx
from reflex.plugins.sitemap import SitemapPlugin

config = rx.Config(
    app_name="warant",
    plugins=[
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(
                appearance="dark",
                accent_color="amber",
                gray_color="mauve",
                radius="medium",
            ),
        ),
    ],
    disable_plugins=[SitemapPlugin],
)
