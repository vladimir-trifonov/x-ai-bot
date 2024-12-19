import os
import time
import random
import json
import logging
import requests
import tempfile
import tweepy
from dotenv import load_dotenv
from news import fetch_latest_crypto_news_cached
from utils import generate_tweet_from_news, ask_openai, generate_text, generate_image, download_image
from database import (
    get_state,
    set_state,
    add_recent_topic,
    get_recent_topics,
    set_json_state,
    get_json_state,
    add_pending_tweet,
    get_pending_tweets,
    remove_pending_tweet,
    increment_retry_count,
    is_duplicate_tweet,
    add_posted_tweet
)
from ratelimit import limits, sleep_and_retry

load_dotenv()

TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
USER_HANDLE = os.getenv("USER_HANDLE")
MAX_POSTS_PER_DAY = int(os.getenv("MAX_POSTS_PER_DAY", "10"))

ONE_HOUR = 60 * 60

client = tweepy.Client(
    bearer_token=TWITTER_BEARER_TOKEN,
    consumer_key=TWITTER_API_KEY,
    consumer_secret=TWITTER_API_SECRET,
    access_token=TWITTER_ACCESS_TOKEN,
    access_token_secret=TWITTER_ACCESS_SECRET,
    wait_on_rate_limit=False,
)

auth = tweepy.OAuth1UserHandler(
    TWITTER_API_KEY,
    TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN,
    TWITTER_ACCESS_SECRET
)
api = tweepy.API(auth, wait_on_rate_limit=False, timeout=10)

def get_my_user_id():
    user_id = get_state("user_id")
    if user_id:
        logging.debug("User ID found in DB, no request needed.")
        return user_id

    logging.debug("Fetching my user id from Twitter...")
    try:
        user = client.get_user(username=USER_HANDLE.strip("@"))
        if user.data:
            logging.debug(f"My user id: {user.data.id}")
            set_state("user_id", str(user.data.id))
            return str(user.data.id)
        else:
            logging.error("Failed to fetch my user id (no data returned).")
    except tweepy.TooManyRequests:
        logging.warning("Rate limit exceeded while fetching user id, skipping.")
    except tweepy.TweepyException as e:
        logging.error(f"Error fetching user id: {e}")
    return None

def get_daily_post_count():
    val = get_state("daily_post_count")
    return int(val) if val else 0

def set_daily_post_count(count):
    set_state("daily_post_count", str(count))

def increment_post_count():
    count = get_daily_post_count()
    count += 1
    set_daily_post_count(count)
    return count

def can_post():
    # Check daily limit
    count = get_daily_post_count()
    return count < MAX_POSTS_PER_DAY

def tweet_latest_crypto_news():
    if not can_post():
        logging.info("Daily limit reached, skipping tweet_latest_crypto_news.")
        return
    news_articles = fetch_latest_crypto_news_cached(api_key=NEWS_API_KEY, user_handle=USER_HANDLE, page_size=5)
    for article in news_articles:
        tweet_text = generate_tweet_from_news(article)
        if is_duplicate_tweet(tweet_text):
            logging.info("Duplicate tweet detected. Skipping this article.")
            continue
        post_id = post_tweet_with_media(tweet_text)
        if post_id:
            add_posted_tweet(tweet_text)
            increment_post_count()
            logging.info(f"Successfully tweeted: {tweet_text}")
            break

def upload_media(image_data):
    try:
        with tempfile.NamedTemporaryFile(delete=True, suffix=".jpg") as tmp_file:
            tmp_file.write(image_data)
            tmp_file.flush()
            logging.debug(f"Uploading media from temporary file: {tmp_file.name}")
            media = api.media_upload(filename=tmp_file.name)
            logging.info(f"Media uploaded with media_id: {media.media_id}")
            return media.media_id
    except Exception as e:
        logging.error(f"Error uploading media: {e}")
    return None

@sleep_and_retry
@limits(calls=17, period=ONE_HOUR * 24)  # 17 calls per 24 hours
def post_tweet_with_media(text: str, image_url=None):
    logging.debug(f"Preparing to post tweet: {text} with image: {image_url}")
    if not text:
        logging.error("No text provided for tweet.")
        return None
    if is_duplicate_tweet(text):
        logging.warning("Duplicate tweet detected. Skipping posting.")
        return None

    media_ids = []
    if image_url:
        img_data = download_image(image_url)
        if img_data:
            media_id = upload_media(img_data)
            if media_id:
                media_ids.append(media_id)
            else:
                logging.warning("Media upload failed, posting tweet without image.")
        else:
            logging.warning("Failed to download image, posting tweet without image.")

    try:
        resp = client.create_tweet(text=text, media_ids=media_ids if media_ids else None)
        if resp.data:
            tweet_id = resp.data['id']
            logging.info(f"Posted tweet {tweet_id} -> {text}, image attached: {bool(media_ids)}")
            add_posted_tweet(text)
            return tweet_id
        else:
            logging.error("Error posting tweet (no data in response).")
            add_pending_tweet(text, image_url)
    except tweepy.TooManyRequests:
        logging.warning("Rate limit exceeded while posting tweet, storing tweet for retry.")
        add_pending_tweet(text, image_url)
    except tweepy.TweepyException as e:
        logging.error(f"Error posting tweet: {e}")
        add_pending_tweet(text, image_url)
    return None

def process_pending_tweets():
    pending = get_pending_tweets()
    if not pending:
        logging.debug("No pending tweets to process.")
        return

    logging.info(f"There are {len(pending)} pending tweet(s). Processing the first one.")

    tweet = pending[0]
    tweet_id = tweet["id"]
    text = tweet["text"]
    image_url = tweet["image_url"]
    retry_count = tweet["retry_count"]

    if retry_count >= 5:
        logging.error(f"Tweet ID {tweet_id} has reached maximum retry attempts. Deleting.")
        remove_pending_tweet(tweet_id)
        return

    logging.debug(f"Retrying tweet ID {tweet_id}: {text} with image: {image_url}")
    success = post_tweet_with_media(text, image_url)
    if success:
        logging.info(f"Successfully posted pending tweet ID {tweet_id}.")
        remove_pending_tweet(tweet_id)
        # If this was a post that appeared on timeline, increment post count if needed
        increment_post_count()
    else:
        logging.warning(f"Failed to post pending tweet ID {tweet_id}. Incrementing retry count.")
        increment_retry_count(tweet_id)

def cached_or_openai_trends():
    trends = get_json_state("cached_trends")
    if not trends:
        prompt = "List 5 currently trending crypto topics as a JSON array of strings."
        content = ask_openai(prompt, max_tokens=100)
        logging.debug(f"OpenAI response: {content}")
        try:
            # Assuming the content is already a JSON string that can be directly evaluated
            if isinstance(content, list):
                set_json_state("cached_trends", content)
                return content
            else:
                logging.error("OpenAI response is not a list.")
                return ["#Crypto", "#Bitcoin", "#Ethereum", "#NFTs", "#DeFi"]
        except Exception as e:
            logging.error(f"Failed to process OpenAI trends: {e}")
            return ["#Crypto", "#Bitcoin", "#Ethereum", "#NFTs", "#DeFi"]
    return trends

def cached_mentions():
    mentions = get_json_state("cached_mentions")
    return mentions if mentions else []

def cached_user_tweets():
    tweets = get_json_state("cached_user_tweets")
    return tweets if tweets else []

def cached_influencers():
    infl = get_json_state("cached_influencers")
    return infl if infl else []

def cached_viral_coins():
    coins = get_json_state("cached_viral_coins")
    return coins if coins else []

def fetch_viral_coins():
    try:
        resp = requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            coins = [item['item']['name'] for item in data.get('coins', [])]
            set_json_state("cached_viral_coins", coins)
            logging.info(f"Fetched viral coins from Coingecko: {coins}")
            return coins
        else:
            logging.error(f"Failed to fetch viral coins, status {resp.status_code}")
    except Exception as e:
        logging.error(f"Error fetching viral coins: {e}")

    prompt = "List 5 fictional viral crypto coin names as a JSON array of strings."
    content = ask_openai(prompt, max_tokens=50)
    try:
        parsed = json.loads(content)
        if isinstance(parsed, list):
            set_json_state("cached_viral_coins", parsed)
            return parsed
    except Exception as e:
        logging.error(f"Failed to parse OpenAI fallback viral coins: {e}")
        return ["CryptoCat", "MoonDoge", "BlockBear", "NFTNyan", "DeFiDragon"]

def cycle_request_type():
    order = ["mentions", "user_tweets", "influencers"]
    current = get_state("request_type")
    if current not in order:
        current = "mentions"
    else:
        idx = order.index(current)
        idx = (idx + 1) % len(order)
        current = order[idx]
    set_state("request_type", current)
    return current

def perform_single_request(user_id):
    rtype = cycle_request_type()
    logging.info(f"Performing single Twitter request for: {rtype}")

    try:
        if rtype == "mentions":
            res = client.get_users_mentions(id=user_id, max_results=10)
            data = [m.text for m in res.data] if res.data else []
            set_json_state("cached_mentions", data)
            if data:
                set_state("LAST_MENTION_TIME", str(time.time()))
        elif rtype == "user_tweets":
            query = f"from:{USER_HANDLE.strip('@')}"
            res = client.search_recent_tweets(query=query, max_results=10)
            data = [t.text for t in res.data] if res.data else []
            set_json_state("cached_user_tweets", data)
        elif rtype == "influencers":
            res = client.search_recent_tweets(
                query="crypto influencer -is:retweet",
                max_results=5,
                expansions=["author_id"],
                user_fields=["username"]
            )
            if res.data and res.includes and 'users' in res.includes:
                usernames = [user.username for user in res.includes['users']]
                influencer_handles = [f"@{username}" for username in usernames]
                set_json_state("cached_influencers", influencer_handles)
                logging.debug(f"Cached influencers: {influencer_handles}")
            else:
                set_json_state("cached_influencers", [])
    except tweepy.TooManyRequests:
        logging.warning("Rate limit exceeded during perform_single_request, skipping this cycle.")
        coins = fetch_viral_coins()
        logging.info(f"Using viral coins fallback: {coins}")
    except tweepy.TweepyException as e:
        logging.error(f"Error performing single request: {e}")
        coins = fetch_viral_coins()
        logging.info(f"Using viral coins fallback: {coins}")

def reply_to_cached_mentions():
    if not can_post():
        logging.info("Daily limit reached, skipping reply_to_cached_mentions.")
        return
    mentions = cached_mentions()
    if not mentions:
        logging.debug("No cached mentions to reply to.")
        return
    mention_text = mentions.pop(0)
    set_json_state("cached_mentions", mentions)
    prompt = f"Reply to this crypto tweet: '{mention_text}'. Add value and positivity."
    reply_text = generate_text(prompt, style="reply")
    post_id = post_tweet_with_media(reply_text)
    if post_id:
        increment_post_count()  # Count replies as posts too if desired
    logging.info("Replied to one cached mention.")

def proactive_engagement_if_no_mentions():
    if not can_post():
        logging.info("Daily limit reached, skipping reply_to_cached_mentions.")
        return
    logging.info("Performing proactive engagement.")
    infl = cached_influencers()
    influencer_name = random.choice(infl) if infl else "@CryptoExpert"

    coins = cached_viral_coins()
    if not coins:
        coins = fetch_viral_coins()

    meme_coin = random.choice(coins) if coins else "#CryptoGem"

    prompt = f"No mentions lately. Tweet about {meme_coin} and give a shoutout to {influencer_name}."
    text = generate_text(prompt, style="tweet")
    image_url = generate_image(f"A cryptocurrency themed image related to {meme_coin} and {influencer_name}")
    post_id = post_tweet_with_media(text, image_url=image_url)
    if post_id:
        increment_post_count()

def tweet_about_crypto_trend():
    if not can_post():
        logging.info("Daily limit reached, skipping tweet_about_crypto_trend.")
        return
    trends = cached_or_openai_trends()
    if not trends:
        logging.debug("No trends found.")
        return

    recent_topics = get_recent_topics(limit=100)
    available_trends = [topic for topic in trends if topic not in recent_topics]

    if not available_trends:
        logging.warning("No new trends available to post.")
        return

    crypto_topic = random.choice(available_trends)
    try:
        response = requests.get(f"https://api.coingecko.com/api/v3/coins/{crypto_topic.lower()}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            current_price = data.get('market_data', {}).get('current_price', {}).get('usd', 'N/A')
            verified_info = f"The current price of {crypto_topic} is ${current_price}."
        else:
            logging.error(f"Failed to fetch data for {crypto_topic} from CoinGecko.")
            verified_info = "Stay tuned for the latest updates on this cryptocurrency!"
    except Exception as e:
        logging.error(f"Error fetching crypto data: {e}")
        verified_info = "Stay tuned for the latest updates on this cryptocurrency!"

    prompt = f"Write a short, insightful tweet about '{crypto_topic}'. Incorporate the following verified information: '{verified_info}'."
    tweet_text = generate_text(prompt, style="tweet")
    image_url = generate_image(f"An illustration representing {crypto_topic}")
    post_id = post_tweet_with_media(tweet_text, image_url=image_url)
    if post_id:
        add_recent_topic(crypto_topic)
        increment_post_count()
        add_recent_topic(crypto_topic)

def promote_account():
    if not can_post():
        logging.info("Daily limit reached, skipping promote_account.")
        return
    user_tweets = cached_user_tweets()
    influencer_tweets = cached_influencers()
    news_snippet = ""
    if influencer_tweets:
        news_snippet = f"Check out these influencer vibes: '{influencer_tweets[0][:60]}...' "

    if not user_tweets:
        prompt = f"Encourage following {USER_HANDLE} for crypto insights. {news_snippet}"
    else:
        example_tweet = random.choice(user_tweets)
        snippet = (example_tweet[:100] + '...') if len(example_tweet) > 100 else example_tweet
        prompt = (f"Encourage following {USER_HANDLE} for crypto insights. Reference: '{snippet}'. "
                  f"{news_snippet} Make them excited to follow.")

    promo_text = generate_text(prompt, style="promo", max_tokens=100)
    image_url = generate_image("A crypto marketing themed illustration")
    post_id = post_tweet_with_media(promo_text, image_url)
    if post_id:
        increment_post_count()

def retweet_popular_crypto_post():
    if not can_post():
        logging.info("Daily limit reached, skipping retweet_popular_crypto_post.")
        return
    text = generate_text("Write a short commentary on a popular crypto tweet you saw recently", style="tweet")
    post_id = post_tweet_with_media(text)
    if post_id:
        increment_post_count()
    logging.info("Simulated retweet by posting a commentary on a popular post.")
