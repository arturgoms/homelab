import asyncio
import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import config
from .navidrome import NavidromeClient
from .lastfm import LastFMClient
from .playlist_gen import PlaylistGenerator
from .history import PlaylistHistory

# Import LLM client conditionally
try:
    from .llm import LLMClient
except ImportError:
    LLMClient = None

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global clients
navidrome_client: NavidromeClient = None
lastfm_client: LastFMClient = None
llm_client: "LLMClient" = None
playlist_history: PlaylistHistory = None
scheduler: AsyncIOScheduler = None


async def run_playlist_generation():
    """Run the playlist generation job."""
    logger.info("Starting scheduled playlist generation...")
    start_time = datetime.now()

    try:
        generator = PlaylistGenerator(
            navidrome_client, lastfm_client, llm_client,
            history=playlist_history,
        )
        results = await generator.generate_and_save_playlists()

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Playlist generation completed in {duration:.1f}s. Results: {results}")

        # Clear Last.fm cache after generation
        lastfm_client.clear_cache()

        return results
    except Exception as e:
        logger.error(f"Playlist generation failed: {e}")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global navidrome_client, lastfm_client, llm_client, playlist_history, scheduler

    # Validate configuration
    if not config.validate():
        logger.error("Invalid configuration. Please check environment variables.")
        raise ValueError("Missing required configuration")

    # Initialize clients
    navidrome_client = NavidromeClient(
        config.NAVIDROME_URL,
        config.NAVIDROME_USER,
        config.NAVIDROME_PASS
    )
    lastfm_client = LastFMClient(config.LASTFM_API_KEY)

    # Initialize playlist history
    playlist_history = PlaylistHistory(
        config.HISTORY_FILE,
        cooldown_days=config.COOLDOWN_DAYS,
    )

    logger.info(f"Initialized Navidrome client for {config.NAVIDROME_URL}")
    logger.info(f"Initialized Last.fm client")
    logger.info(f"Initialized playlist history (cooldown: {config.COOLDOWN_DAYS} days)")

    # Initialize LLM client if enabled
    if config.LLM_ENABLED and LLMClient:
        llm_client = LLMClient(config.LLM_BASE_URL, config.LLM_MODEL)
        if await llm_client.health_check():
            logger.info(f"Initialized LLM client for {config.LLM_BASE_URL}")
            if config.LLM_AUTO_MOODS:
                logger.info("LLM auto-mood discovery enabled")
            else:
                logger.info(f"Mood playlists configured: {config.MOOD_PLAYLISTS}")
        else:
            logger.warning(f"LLM server not accessible at {config.LLM_BASE_URL}, mood playlists disabled")
            await llm_client.close()
            llm_client = None
    else:
        logger.info("LLM integration disabled")

    # Setup scheduler
    scheduler = AsyncIOScheduler()

    # Parse cron expression
    cron_parts = config.SCHEDULE_CRON.split()
    if len(cron_parts) == 5:
        trigger = CronTrigger(
            minute=cron_parts[0],
            hour=cron_parts[1],
            day=cron_parts[2],
            month=cron_parts[3],
            day_of_week=cron_parts[4]
        )
        scheduler.add_job(run_playlist_generation, trigger, id="daily_mix")
        scheduler.start()
        logger.info(f"Scheduled playlist generation: {config.SCHEDULE_CRON}")
    else:
        logger.warning(f"Invalid cron expression: {config.SCHEDULE_CRON}")

    yield

    # Cleanup
    scheduler.shutdown()
    await navidrome_client.close()
    await lastfm_client.close()
    if llm_client:
        await llm_client.close()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Daily Mix",
    description="Automatic playlist generator for Navidrome",
    version="2.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "daily-mix",
        "version": "2.0.0",
        "navidrome_url": config.NAVIDROME_URL,
        "schedule": config.SCHEDULE_CRON,
    }


@app.get("/health")
async def health():
    """Health check for Docker."""
    return {"status": "ok"}


@app.post("/generate")
async def generate_playlists():
    """Manually trigger playlist generation."""
    try:
        results = await run_playlist_generation()
        return {
            "status": "success",
            "playlists": results
        }
    except Exception as e:
        logger.error(f"Manual generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
async def get_status():
    """Get service status and next scheduled run."""
    next_run = None
    if scheduler:
        job = scheduler.get_job("daily_mix")
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat()

    # Get current mood categories
    current_moods = []
    if config.LLM_AUTO_MOODS and os.path.exists(config.MOOD_CONFIG_FILE):
        try:
            import json
            with open(config.MOOD_CONFIG_FILE, "r") as f:
                mood_data = json.load(f)
            current_moods = mood_data.get("moods", [])
        except Exception:
            pass
    elif not config.LLM_AUTO_MOODS:
        current_moods = config.MOOD_PLAYLISTS

    # Get cooldown stats
    cooldown_stats = {}
    if playlist_history:
        cooldown_stats = playlist_history.get_stats()

    return {
        "status": "running",
        "schedule_cron": config.SCHEDULE_CRON,
        "next_run": next_run,
        "playlist_size": config.PLAYLIST_SIZE,
        "for_you_name": config.PLAYLIST_FOR_YOU_NAME,
        "discover_name": config.PLAYLIST_DISCOVER_NAME,
        "llm_enabled": llm_client is not None,
        "llm_auto_moods": config.LLM_AUTO_MOODS,
        "current_moods": current_moods,
        "cooldown_days": config.COOLDOWN_DAYS,
        "cooldown_stats": cooldown_stats,
    }


@app.post("/moods/reset")
async def reset_moods():
    """Force LLM to re-discover mood categories on next generation."""
    if not config.LLM_AUTO_MOODS:
        raise HTTPException(status_code=400, detail="LLM auto-moods not enabled")

    if os.path.exists(config.MOOD_CONFIG_FILE):
        os.remove(config.MOOD_CONFIG_FILE)
        logger.info("Mood config reset — will re-discover on next generation")
        return {"status": "reset", "message": "Mood config cleared. New moods will be discovered on next generation."}

    return {"status": "ok", "message": "No mood config to reset."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
