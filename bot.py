def send_telegram_photo(photo_path, caption=None):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
    with open(photo_path, "rb") as photo:
        r = requests.post(
            url,
            data={
                "chat_id": TG_CHAT_ID,
                "caption": caption or "",
            },
            files={"photo": photo},
            timeout=60,
        )
    r.raise_for_status()
    return r.json()
