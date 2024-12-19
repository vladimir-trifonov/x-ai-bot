# X-AI-BOT

X-AI-BOT is a Twitter bot designed to keep you updated with the latest cryptocurrency news. It fetches real-time crypto news from reliable sources and shares insightful tweets, replies to mentions, and promotes your crypto content to engage with the crypto community effectively.

## 🚀 Features

- **Dynamic Content Generation:** Fetches the latest crypto news and generates engaging tweets.
- **Automated Replies:** Responds to mentions and interactions to boost engagement.
- **Promotional Tweets:** Periodically promotes your account to attract more followers.
- **Rate Limiting & Error Handling:** Ensures smooth operation by handling API rate limits and errors gracefully.
- **Duplicate Prevention:** Avoids posting duplicate content to maintain tweet uniqueness.

## 🛠 Installation

Follow these steps to set up and run X-AI-BOT on your local machine.

### 1. Prerequisites

- **Python 3.11.3:** Ensure you have Python installed. You can use [pyenv](https://github.com/pyenv/pyenv) for managing Python versions.

  ```bash
  # Install pyenv (if not already installed)
  curl https://pyenv.run | bash

  # Restart your shell
  exec "$SHELL"

  # Install Python 3.11.3
  pyenv install 3.11.3

  # Set Python version globally or locally
  pyenv global 3.11.3
  ```

- **Git:** To clone the repository.

### 2. Clone the Repository

```bash
git clone https://github.com/vladimir-trifonov/x-ai-bot.git
cd x-ai-bot
```

### 3. Set Up a Virtual Environment

It's recommended to use a virtual environment to manage dependencies.

```bash
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
```

### 4. Install Dependencies

Install the required Python packages using `pip`:

```bash
pip install -r requirements.txt
```

## 🔧 Configuration

X-AI-BOT requires certain API keys and configuration settings. Follow these steps to set them up.

### 1. Create a `.env` File

Create a `.env` file in the root directory of the project to store your environment variables securely.

```bash
touch .env
```

### 2. Populate the `.env` File

Add the following variables to your `.env` file with your respective API keys and credentials:

```env
# Twitter API Credentials
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
TWITTER_API_KEY=your_twitter_api_key
TWITTER_API_SECRET=your_twitter_api_secret
TWITTER_ACCESS_TOKEN=your_twitter_access_token
TWITTER_ACCESS_SECRET=your_twitter_access_secret
USER_HANDLE=your_twitter_handle

# News API Key
NEWSAPI_KEY=your_newsapi_key

# OpenAI API Key (if using OpenAI for content generation)
OPENAI_API_KEY=your_openai_api_key

# Email Credentials (for error notifications, optional)
FROM_EMAIL=your_email@example.com
EMAIL_PASSWORD=your_email_password
TO_EMAIL=recipient_email@example.com
```

**📌 Note:**
- Replace `your_twitter_bearer_token`, `your_twitter_api_key`, etc., with your actual credentials.
- Ensure that the `.env` file is **not** tracked by Git to keep your credentials secure. The project should already have a `.gitignore` entry for `.env`.

## 🏃‍♂️ Usage

Once you've set up the environment and configured the necessary API keys, you can start the bot.

### 1. Initialize the Database

Before running the bot for the first time, initialize the database:

```bash
python database.py
```

### 2. Run the Bot

Start the bot using the `main.py` script:

```bash
python main.py
```

The bot will start its main loop, fetching news, posting tweets, replying to mentions, and performing promotional activities based on the configured intervals.

## 📋 Project Structure

```
x-ai-bot/
├── bot.py
├── database.py
├── news.py
├── utils.py
├── main.py
├── requirements.txt
├── .env
├── README.md
└── ...
```

- **bot.py:** Contains functions related to Twitter interactions.
- **database.py:** Handles database operations to track posted tweets and manage state.
- **news.py:** Manages fetching and parsing crypto news from NewsAPI.
- **utils.py:** Utility functions for generating tweet content and handling duplicates.
- **main.py:** The main entry point that runs the bot's loop.
- **requirements.txt:** Lists all Python dependencies.
- **.env:** Stores environment variables (not tracked by Git).

## 🐞 Troubleshooting

### 1. `HTTP 429 Too Many Requests` Error

**Cause:** Exceeding the API's rate limits.

**Solution:**

1. **Wait for Rate Limits to Reset:**
   - Check the `x-rate-limit-reset` timestamp and wait until it resets.

2. **Implement Rate Limiting in Code:**
   - Use libraries like `ratelimit` or `tenacity` to manage request rates.

3. **Optimize API Requests:**
   - Cache responses and avoid unnecessary requests.

4. **Upgrade API Plan:**
   - If you frequently hit rate limits, consider upgrading to a higher-tier plan.

## 📝 Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

**Happy Tweeting! 🚀**

For any further assistance or questions, feel free to reach out.