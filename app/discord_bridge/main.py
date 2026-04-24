from __future__ import annotations

import logging

from app.discord_bridge.config import load_bridge_config_from_env
from app.discord_bridge.runtime import StockAgentDiscordBot


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = load_bridge_config_from_env()
    bot = StockAgentDiscordBot(config)
    bot.run()


if __name__ == "__main__":
    main()
