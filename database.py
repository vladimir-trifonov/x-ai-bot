import sqlite3
import json
import hashlib

DB_NAME = "bot_state.db"

def get_tweet_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS state (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS recent_topics (
        topic TEXT PRIMARY KEY
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS pending_tweets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL,
        image_url TEXT,
        retry_count INTEGER DEFAULT 0
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS posted_tweets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tweet_text TEXT NOT NULL,
        tweet_hash TEXT,
        posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS prompt_examples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        style TEXT NOT NULL  -- "tweet", "reply", "promo", etc.
    )
    """)
    conn.commit()
    conn.close()

def get_state(key):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT value FROM state WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def set_state(key, value):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("REPLACE INTO state (key,value) VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()

def add_recent_topic(topic, max_limit=100):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO recent_topics (topic) VALUES (?)", (topic,))
    conn.commit()
    c.execute("SELECT COUNT(*) FROM recent_topics")
    count = c.fetchone()[0]
    if count > max_limit:
        c.execute("""
        DELETE FROM recent_topics
        WHERE rowid IN (
            SELECT rowid FROM recent_topics
            ORDER BY rowid ASC
            LIMIT ?
        )
        """, (count - max_limit,))
        conn.commit()
    conn.close()

def get_recent_topics(limit=100):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT topic FROM recent_topics ORDER BY rowid DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]

def set_json_state(key, data):
    value = json.dumps(data)
    set_state(key, value)

def get_json_state(key):
    val = get_state(key)
    if val:
        return json.loads(val)
    return None

def add_pending_tweet(text, image_url=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO pending_tweets (text, image_url, retry_count) VALUES (?, ?, 0)", (text, image_url))
    conn.commit()
    conn.close()

def get_pending_tweets():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, text, image_url, retry_count FROM pending_tweets ORDER BY id ASC")
    rows = c.fetchall()
    conn.close()
    return [{"id": row[0], "text": row[1], "image_url": row[2], "retry_count": row[3]} for row in rows]

def increment_retry_count(tweet_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE pending_tweets SET retry_count = retry_count + 1 WHERE id = ?", (tweet_id,))
    conn.commit()
    conn.close()

def remove_pending_tweet(tweet_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM pending_tweets WHERE id=?", (tweet_id,))
    conn.commit()
    conn.close()

def add_posted_tweet(text):
    tweet_hash = get_tweet_hash(text)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO posted_tweets (tweet_text, tweet_hash) VALUES (?, ?)", (text, tweet_hash))
    conn.commit()
    conn.close()

def is_duplicate_tweet(text):
    tweet_hash = get_tweet_hash(text)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT 1 FROM posted_tweets WHERE tweet_hash = ?", (tweet_hash,))
    result = c.fetchone()
    conn.close()
    return result is not None

def get_recent_posted_tweets(limit=100):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT tweet_text FROM posted_tweets ORDER BY posted_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]

def add_prompt_example(role, content, style="tweet"):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO prompt_examples (role, content, style) VALUES (?, ?, ?)", (role, content, style))
    conn.commit()
    conn.close()

def get_prompt_examples(style="tweet", limit=5):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT role, content FROM prompt_examples WHERE style=? ORDER BY RANDOM() LIMIT ?", (style, limit))
    rows = c.fetchall()
    conn.close()
    return [{"role": row[0], "content": row[1]} for row in rows]

def delete_prompt_examples(style="tweet", limit=5):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM prompt_examples WHERE style=? ORDER BY rowid DESC LIMIT ?", (style, limit))
    conn.commit()
    conn.close()
