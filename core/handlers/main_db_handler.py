# (c) @AbirHasan2005 | Updated by GPT-5 (2025)
# Modern async database handler for Telegram Video Watermark Bot

import asyncio
import logging
from configs import Config
from core.database import Database

logger = logging.getLogger(__name__)

# Global database instance placeholder
db: Database


async def init_db() -> Database:
    """
    Initialize MongoDB connection asynchronously.
    Ensures indexes are created before the bot starts.
    """
    global db
    try:
        logger.info("🔌 Connecting to MongoDB...")
        db = Database(Config.DATABASE_URL, Config.BOT_USERNAME)
        await db.init_indexes()
        logger.info("✅ MongoDB connection established successfully.")
        return db
    except Exception as e:
        logger.error(f"❌ Failed to connect to MongoDB: {e}")
        raise


# Optional startup hook
async def startup():
    """Run on bot startup to ensure DB connection is alive."""
    try:
        await init_db()
    except Exception as e:
        logger.critical(f"🚫 Database startup failed: {e}")
        raise


# Backward compatibility for older imports
# (Allows using `from core.handlers.main_db_handler import db`)
try:
    asyncio.get_event_loop().run_until_complete(init_db())
except RuntimeError:
    # If event loop already running (e.g., in async context)
    pass
