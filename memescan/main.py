"""
MemeScan - Main Entry Point
Runs both Telegram bot and Twitter auto-poster.
"""
import os
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv

from .bot import router, get_client
from .twitter import memescan_twitter, start_twitter_auto_poster

load_dotenv()


async def on_startup(bot: Bot):
    """Called when bot starts."""
    print("MemeScan bot starting up...")

    # Start Twitter auto-poster in background
    twitter_enabled = os.getenv("MEMESCAN_TWITTER_ENABLED", "false").lower() == "true"
    if twitter_enabled:
        memescan_twitter.initialize()
        asyncio.create_task(start_twitter_auto_poster())
        print("Twitter auto-poster started")


async def on_shutdown(bot: Bot):
    """Called when bot shuts down."""
    print("MemeScan shutting down...")
    memescan_twitter.stop()
    client = get_client()
    await client.close()


async def run_polling():
    """Run bot with polling (for development/testing)."""
    token = os.getenv("MEMESCAN_BOT_TOKEN")
    if not token:
        print("ERROR: MEMESCAN_BOT_TOKEN not set")
        print("Set it in .env file or environment")
        return

    bot = Bot(token=token)
    dp = Dispatcher()
    dp.include_router(router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    print("Starting MemeScan in polling mode...")
    print("Commands: /start, /trending, /new, /check, /pools, /help")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


async def run_webhook(host: str = "0.0.0.0", port: int = 8080):
    """Run bot with webhook (for production)."""
    token = os.getenv("MEMESCAN_BOT_TOKEN")
    webhook_url = os.getenv("MEMESCAN_WEBHOOK_URL")

    if not token:
        print("ERROR: MEMESCAN_BOT_TOKEN not set")
        return

    if not webhook_url:
        print("ERROR: MEMESCAN_WEBHOOK_URL not set")
        return

    bot = Bot(token=token)
    dp = Dispatcher()
    dp.include_router(router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Set webhook
    webhook_path = f"/webhook/{token}"
    await bot.set_webhook(f"{webhook_url}{webhook_path}")

    # Setup aiohttp app
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=webhook_path)

    # Health check endpoint
    async def health(request):
        return web.Response(text="OK")

    app.router.add_get("/health", health)

    print(f"Starting MemeScan webhook server on {host}:{port}")

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()

    # Keep running
    try:
        await asyncio.Event().wait()
    finally:
        await bot.session.close()
        await runner.cleanup()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="MemeScan - TON Meme Terminal")
    parser.add_argument(
        "--mode",
        choices=["polling", "webhook"],
        default="polling",
        help="Bot mode (default: polling)"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Webhook host")
    parser.add_argument("--port", type=int, default=8080, help="Webhook port")

    args = parser.parse_args()

    if args.mode == "webhook":
        asyncio.run(run_webhook(args.host, args.port))
    else:
        asyncio.run(run_polling())


if __name__ == "__main__":
    main()
