import os
import openai
import requests
import logging
from dotenv import load_dotenv
from database import get_prompt_examples

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

def ask_openai(prompt, max_tokens=150, temperature=0.9):
    """
    Sends a prompt to OpenAI and returns the generated response.
    """
    logging.debug(f"Asking OpenAI with prompt: {prompt}")
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=1.0,
            frequency_penalty=0.2,
            presence_penalty=0.2
        )
        content = response.choices[0].message.content
        logging.debug(f"OpenAI response: {content}")
        return content
    except Exception as e:
        logging.error(f"Error with OpenAI ChatCompletion: {e}")
        return ""

def generate_text(prompt: str, style: str = "tweet", max_tokens: int = 150, temperature: float = 0.9):
    """
    Generates text based on the given prompt and style.
    """
    logging.debug(f"Generating text with style='{style}', prompt='{prompt}'")
    
    # Incorporate examples to guide the AI
    examples = get_prompt_examples(style=style, limit=5)

    messages = []

    # Insert the retrieved examples (which contain role and content)
    # Ensure that the examples have roles like "assistant" or "user" depending on how you saved them.
    # For simplicity, let's assume we saved them as assistant role examples.
    messages.extend(examples)
    
    # Finally add the user prompt
    messages.append({"role": "user", "content": prompt})
    
    # Combine examples with the actual prompt
    system_role_content = "You are a knowledgeable and friendly crypto expert who writes engaging and informative tweets and replies."
    messages = [{"role": "system", "content": system_role_content}]
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=1.0,
            frequency_penalty=0.2,
            presence_penalty=0.2
        )
        text = response.choices[0].message.content
        logging.debug(f"Generated text: {text}")
        return text[:280]  # Ensure tweet length limit
    except Exception as e:
        logging.error(f"Error generating text with OpenAI: {e}")
        return ""

def generate_image(prompt: str):
    """
    Generates an image based on the given prompt using OpenAI's DALL·E.
    """
    logging.debug(f"Generating image with prompt: {prompt}")
    try:
        image_response = openai.images.generate(
            prompt=prompt,
            n=1,
            size="512x512"
        )
        image_url = image_response.data[0].url
        logging.debug(f"Generated image URL: {image_url}")
        return image_url
    except Exception as e:
        logging.error(f"Error generating image with OpenAI: {e}")
        return None

def download_image(url):
    """
    Downloads an image from the given URL and returns the binary content.
    """
    logging.debug(f"Downloading image from URL: {url}")
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            logging.debug("Image downloaded successfully.")
            return resp.content
        logging.error(f"Failed to download image, status code: {resp.status_code}")
    except Exception as e:
        logging.error(f"Error downloading image: {e}")
    return None

def generate_tweet_from_news(article):
    """
    Generates a tweet text based on a news article using GPT for summarization.
    """
    title = article.get("title")
    description = article.get("description")
    url = article.get("url")
    source = article.get("source")
    
    prompt = f"Summarize the following crypto news into a concise tweet under 280 characters:\nTitle: {title}\nDescription: {description}\nURL: {url}"
    
    summary = generate_text(prompt, style="tweet")  # Assuming generate_text interacts with OpenAI API
    
    # Append source hashtag
    tweet = f"{summary}\n#CryptoNews #{source.replace(' ', '')}"
    
    return tweet[:280]
