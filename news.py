import requests
import logging
import time
from cachetools import TTLCache, cached
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from database import add_prompt_example, delete_prompt_examples

news_cache = TTLCache(maxsize=100, ttl=3600)

@cached(cache=news_cache)
def fetch_latest_crypto_news_cached(api_key, user_handle, query="cryptocurrency", language="en", page_size=10):
    return fetch_and_process_crypto_news(api_key, user_handle, query, language, page_size)

@retry(
    retry=retry_if_exception_type(requests.exceptions.RequestException),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    stop=stop_after_attempt(5)
)
def fetch_and_process_crypto_news(api_key, user_handle, query="cryptocurrency", language="en", page_size=10):
    """
    Fetches and processes the latest crypto news articles from NewsAPI.
    """
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "language": language,
        "sortBy": "publishedAt",
        "pageSize": page_size,
        "apiKey": api_key
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            logging.warning(f"Rate limit exceeded. Retrying after {retry_after} seconds.")
            time.sleep(retry_after)
            return fetch_and_process_crypto_news(api_key, user_handle, query, language, page_size)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "ok":
            logging.error(f"Error fetching news: {data.get('message')}")
            return []

        articles = data.get("articles", [])
        parsed_articles = process_articles(articles, user_handle)
        return parsed_articles

    except requests.exceptions.RequestException as e:
        logging.error(f"Request exception while fetching news: {e}")
        return []
    except ValueError as ve:
        logging.error(f"JSON decoding failed: {ve}")
        return []

def process_articles(articles, user_handle):
    """
    Processes articles and adds them as prompt examples in the database.
    """
    parsed_articles = []
    for article in articles:
        if not article.get("title") or not article.get("description"):
            continue

        title = article["title"]
        description = article["description"]
        
        example_tweet = f"\ud83d\uddde {title}\n{description}\n{user_handle}"
        example_tweet = example_tweet.encode("utf-16", "surrogatepass").decode("utf-16")

        add_prompt_example("assistant", example_tweet, style="tweet")
        parsed_articles.append({
            "title": title,
            "description": description,
            "url": article.get("url"),
            "source": article.get("source", {}).get("name"),
            "published_at": article.get("publishedAt")
        })

    logging.info(f"Processed {len(parsed_articles)} crypto news articles.")
    return parsed_articles

def refresh_prompt_examples(api_key, user_handle, query="cryptocurrency", language="en", limit=10, page_size=5):
    """
    Deletes the older prompt examples and refreshes with the latest crypto news articles.
    """
    delete_prompt_examples(style="tweet", limit=limit)
    fetch_and_process_crypto_news(api_key, user_handle, query, language, page_size)
    