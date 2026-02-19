"""
Скрипт: ссылка на коммит в GitHub → дифф → генерация твита (OpenRouter) → подтверждение → пост в X.
Запуск: python post_tweet.py
Переменные в .env: OPEN_ROUTER_API_KEY, X_CONSUMER_KEY, X_CONSUMER_SECRET,
                   X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET.
"""

import os
import sys

import httpx
from dotenv import load_dotenv
from requests_oauthlib import OAuth1Session

load_dotenv()

DIFF_MAX_CHARS = 8000
TWEET_MAX_CHARS = 280

SYSTEM_PROMPT = """You write short, catchy tweets about code changes in English.
Style: 1–2 short sentences, friendly and clear. One optional hashtag: #buildinpublic.
Mention what changed and impact, not low-level code details. No code blocks. Do tweet some calm and mysterious. Ignore md files from diff. Add to tweet link https://github.com/maxphoton/firefox-translate-ext"""

USER_PROMPT_TEMPLATE = """Below is a Git diff from a GitHub commit. Write exactly ONE tweet (max {max_chars} characters) in the style above. Output only the tweet text, no quotes or explanation.

Diff:
{diff}"""


def get_diff_from_github(url: str) -> str:
    """Скачивает raw diff по ссылке на коммит (добавляет .diff если нужно)."""
    url = url.strip().rstrip("/")
    if not url.endswith(".diff"):
        url = url + ".diff"
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text


def build_prompt(diff: str) -> tuple[str, str]:
    """Собирает system и user сообщения для OpenRouter."""
    truncated = diff[:DIFF_MAX_CHARS]
    if len(diff) > DIFF_MAX_CHARS:
        truncated += "\n\n[... diff truncated ...]"
    user_content = USER_PROMPT_TEMPLATE.format(
        max_chars=TWEET_MAX_CHARS, diff=truncated
    )
    return SYSTEM_PROMPT, user_content


def generate_tweet(diff: str) -> str:
    """Генерирует текст твита через OpenRouter."""
    api_key = os.getenv("OPEN_ROUTER_API_KEY")
    if not api_key:
        raise SystemExit("OPEN_ROUTER_API_KEY not set in .env")

    system, user = build_prompt(diff)
    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": 150,
        "temperature": 0.7,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    timeout = 90.0
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                break
        except (httpx.ConnectTimeout, httpx.ReadTimeout) as e:
            last_error = e
            if attempt == 0:
                print("OpenRouter timeout, retrying...")
            else:
                raise SystemExit(f"OpenRouter request failed: {e}") from e
    else:
        raise SystemExit(f"OpenRouter request failed: {last_error}") from last_error
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    tweet = content.strip().strip('"')
    if len(tweet) > TWEET_MAX_CHARS:
        tweet = tweet[: TWEET_MAX_CHARS - 3] + "..."
    return tweet


def post_tweet(text: str) -> None:
    """Публикует твит в X через OAuth 1.0a."""
    consumer_key = os.getenv("X_CONSUMER_KEY")
    consumer_secret = os.getenv("X_CONSUMER_SECRET")
    access_token = os.getenv("X_ACCESS_TOKEN")
    access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET")
    missing = []
    if not consumer_key:
        missing.append("X_CONSUMER_KEY")
    if not consumer_secret:
        missing.append("X_CONSUMER_SECRET")
    if not access_token:
        missing.append("X_ACCESS_TOKEN")
    if not access_token_secret:
        missing.append("X_ACCESS_TOKEN_SECRET")
    if missing:
        raise SystemExit(f"Missing in .env: {', '.join(missing)}")

    oauth = OAuth1Session(
        consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=access_token,
        resource_owner_secret=access_token_secret,
    )
    resp = oauth.post(
        "https://api.twitter.com/2/tweets",
        json={"text": text},
    )
    if resp.status_code != 201:
        if resp.status_code == 402:
            raise SystemExit(
                "X API 402: No credits left. Add payment or credits in "
                "developer.x.com → your app → Billing / Subscription."
            )
        raise SystemExit(f"X API error {resp.status_code}: {resp.text}")
    result = resp.json()
    tweet_id = result.get("data", {}).get("id", "")
    print(f"Posted. Tweet ID: {tweet_id}")


def main() -> None:
    print("Enter GitHub commit URL (e.g. https://github.com/owner/repo/commit/abc123):")
    url = input().strip()
    if not url or "github.com" not in url:
        print("Invalid URL.")
        sys.exit(1)

    print("Fetching diff...")
    diff = get_diff_from_github(url)
    if not diff.strip():
        print("Empty diff.")
        sys.exit(1)

    print("Generating tweet...")
    tweet = generate_tweet(diff)
    print("\n--- Generated tweet ---")
    print(tweet)
    print("---\n")

    answer = input("Post this tweet? (y/n): ").strip().lower()
    if answer != "y":
        print("Cancelled.")
        return
    post_tweet(tweet)


if __name__ == "__main__":
    main()
