import time
import logging
from database import init_db, get_state, set_state
from bot import (
    perform_single_request,
    reply_to_cached_mentions,
    tweet_about_crypto_trend,
    promote_account,
    retweet_popular_crypto_post,
    proactive_engagement_if_no_mentions,
    get_my_user_id,
    tweet_latest_crypto_news,
    process_pending_tweets
)
from news import refresh_prompt_examples
import os
from dotenv import load_dotenv
import signal
import sys
import datetime

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

REQUEST_INTERVAL = int(os.getenv("REQUEST_INTERVAL", "1200"))         # 20 minutes
POST_INTERVAL = int(os.getenv("POST_INTERVAL", "3600"))               # 1 hour
MAX_POSTS_PER_DAY = int(os.getenv("MAX_POSTS_PER_DAY", "12"))         # Default 12 if not set

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
USER_HANDLE = os.getenv("USER_HANDLE")

def signal_handler(sig, frame):
    logging.info("Shutdown signal received. Exiting gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def get_daily_post_count():
    val = get_state("daily_post_count")
    return int(val) if val else 0

def set_daily_post_count(count):
    set_state("daily_post_count", str(count))

def reset_daily_post_count():
    set_daily_post_count(0)

def get_daily_reset_time():
    val = get_state("daily_reset_time")
    if val:
        return float(val)
    else:
        # Set reset time to next midnight UTC
        now = datetime.datetime.now(datetime.UTC)
        tomorrow = now + datetime.timedelta(days=1)
        midnight = datetime.datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0)
        reset_ts = midnight.timestamp()
        set_state("daily_reset_time", str(reset_ts))
        return reset_ts

def maybe_reset_daily_limit():
    # Check if current time > daily_reset_time, if so reset
    now = time.time()
    reset_ts = get_daily_reset_time()
    if now > reset_ts:
        logging.info("Daily post count limit resetting.")
        reset_daily_post_count()
        # Set next reset time
        now_dt = datetime.datetime.now(datetime.UTC)
        tomorrow = now_dt + datetime.timedelta(days=1)
        midnight = datetime.datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0)
        next_reset_ts = midnight.timestamp()
        set_state("daily_reset_time", str(next_reset_ts))

def increment_post_count():
    count = get_daily_post_count()
    count += 1
    set_daily_post_count(count)
    return count

def can_post():
    # Check daily limit
    count = get_daily_post_count()
    return count < MAX_POSTS_PER_DAY

# Define the tasks we want to rotate through
TASKS = [
    tweet_latest_crypto_news,
    tweet_about_crypto_trend,
    retweet_popular_crypto_post,
    promote_account,
    reply_to_cached_mentions,
    proactive_engagement_if_no_mentions,
    process_pending_tweets
]

def get_next_task_index():
    val = get_state("task_index")
    if val is None:
        set_state("task_index", "0")
        return 0
    return int(val)

def set_next_task_index(idx):
    set_state("task_index", str(idx))

def perform_post_task():
    posted = False
    idx = get_next_task_index()
    task = TASKS[idx]
    logging.info(f"Rotating tasks. Current task: {task.__name__}")
    
    if can_post():
        before_count = get_daily_post_count()
        task()
        after_count = get_daily_post_count()

        posted = after_count > before_count
        
        if posted:
            logging.info("A new tweet was posted by the task.")
        else:
            logging.info("The task did not post a new tweet.")
    else:
        logging.info("Reached daily post limit. Skipping posting tasks.")

    # Move to next task
    next_idx = (idx + 1) % len(TASKS)
    set_next_task_index(next_idx)

    return posted

def perform_daily_prompt_refresh():
    last_refresh_date = get_state("last_prompt_refresh_date")
    today_date_str = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d")
    
    if last_refresh_date != today_date_str:
        logging.info("Refreshing prompt examples for the day...")
        refresh_prompt_examples(api_key=NEWS_API_KEY, user_handle=USER_HANDLE, limit=5, page_size=5)
        set_state("last_prompt_refresh_date", today_date_str)
    else:
        logging.debug("Prompt examples already refreshed today.")

if __name__ == "__main__":
    logging.info("Initializing database...")
    init_db()

    # On startup, maybe reset daily limit if needed
    maybe_reset_daily_limit()

    last_request = get_state("last_request_time")
    if last_request:
        last_request = float(last_request)
    else:
        last_request = 0.0

    last_post = get_state("last_post_time")
    if last_post:
        last_post = float(last_post)
    else:
        last_post = 0.0

    last_promo_tweet = time.time()
    last_retweet = time.time()
    last_news_tweet = time.time()

    logging.info("Bot starting main loop...")
    while True:
        now = time.time()

        # Check if daily limit needs resetting
        maybe_reset_daily_limit()

        # Perform daily prompt refresh
        perform_daily_prompt_refresh()

        # Attempt to get USER_ID if not set
        user_id = get_state("user_id")
        if not user_id:
            logging.debug("User ID not found in DB, attempting to fetch...")
            user_id = get_my_user_id()
            if user_id:
                logging.info("Fetched user_id and stored in DB.")
            else:
                logging.warning("Could not fetch user_id, proceeding without it.")

        # Perform a single request cycle if needed
        if user_id:
            if (now - last_request) > REQUEST_INTERVAL:
                logging.debug("Time to perform a single Twitter API request...")
                perform_single_request(user_id)
                last_request = now
                set_state("last_request_time", str(now))
            else:
                logging.debug("Not time for a new Twitter request yet, using cached data...")

            if (now - last_post) > POST_INTERVAL:
                logging.debug("Time to perform a single Twitter API reply...")
                posted = perform_post_task()
                if posted:
                  last_post = now
                  set_state("last_post_time", str(now))
            else:
                logging.debug("Not time for a new Twitter post yet...")

        logging.debug("Sleeping until next iteration...")
        time.sleep(min(REQUEST_INTERVAL, POST_INTERVAL))
