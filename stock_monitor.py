import os
import requests

if __name__ == "__main__":
    bot_token = os.environ["BOT_TOKEN"]
    chat_id = os.environ["CHAT_ID"]

    response = requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": "Test message from GitHub Actions",
        },
        timeout=30,
    )

    print(response.status_code)
    print(response.text)
    response.raise_for_status()
