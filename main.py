import asyncio
import os
from bot import AgencyBot
from config import Logger, DiscordToken

async def main() -> None:
    Bot = AgencyBot()
    async with Bot:
        if not DiscordToken:
            Logger.critical("DISCORD_TOKEN environment variable not found in environment or .env file.")
            return
        await Bot.start(DiscordToken)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
