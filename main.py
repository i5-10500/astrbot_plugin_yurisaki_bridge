"""AstrBot plugin entry point for Yurisaki Bridge."""

from astrbot.api import logger
from astrbot.api.star import Context, Star

from yurisaki_bridge import __version__


class YurisakiBridgePlugin(Star):
    """Own the AstrBot-facing lifecycle for the bridge."""

    def __init__(self, context: Context) -> None:
        super().__init__(context)

    async def initialize(self) -> None:
        """Initialize plugin services after AstrBot loads the plugin."""
        logger.info(f"Yurisaki Bridge {__version__} initialized")

    async def terminate(self) -> None:
        """Release plugin resources during unload or hot reload."""
        logger.info("Yurisaki Bridge terminated")
