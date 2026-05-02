from typing import Optional

import requests

from config import TELEGRAM_BOT_TOKEN, TG_CHAT_ID


def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": TG_CHAT_ID,
            "text": text,
        },
        timeout=30,
    )

    response.raise_for_status()


def send_telegram_photo(photo_path: str, caption: Optional[str] = None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"

    with open(photo_path, "rb") as file:
        response = requests.post(
            url,
            data={
                "chat_id": TG_CHAT_ID,
                "caption": caption or "",
            },
            files={"photo": file},
            timeout=60,
        )

    response.raise_for_status()


def send_error_to_telegram(error_text: str):
    safe_text = f"❌ Portfolio bot error\n\n{error_text[:3500]}"

    try:
        send_telegram_message(safe_text)
    except Exception:
        print("Failed sending error to Telegram")
