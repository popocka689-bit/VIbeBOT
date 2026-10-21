#!/usr/bin/env python3
import html
import os
import sys
import urllib.parse
import urllib.request
import json

def main():
    bot_token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.environ.get("CHAT_ID") or "").strip()
    app_name = (os.environ.get("APP_NAME") or "VibeApp").strip()
    status = (os.environ.get("STATUS") or "started").strip()

    if not bot_token or not chat_id:
        print("Missing TELEGRAM_BOT_TOKEN or CHAT_ID, skipping notification.")
        return

    safe_name = html.escape(app_name)

    if status == "started":
        text = (
            f"⚙️ <b>Сборщик запустился!</b>\n\n"
            f"📱 Приложение: <b>{safe_name}</b>\n"
            f"⏳ Начинаем скачивание файлов и компиляцию APK через Gradle...\n"
            f"Это обычно занимает 1-2 минуты. Готовый файл придет сюда."
        )
    elif status == "failed":
        error_details = os.environ.get("ERROR_MESSAGE", "")
        safe_err = html.escape(error_details) if error_details else ""
        text = (
            f"❌ <b>Ошибка сборки!</b>\n\n"
            f"К сожалению, сборка приложения <b>{safe_name}</b> завершилась неудачей.\n"
            f"Проверь структуру архива: в корне (или вложенной папке) обязательно должен быть <code>index.html</code>."
        )
        if safe_err:
            text += f"\n\nДетали: <pre>{safe_err}</pre>"
    else:
        text = f"Статус сборки <b>{safe_name}</b>: {status}"

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"Telegram notification sent successfully: {resp.status}")
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
