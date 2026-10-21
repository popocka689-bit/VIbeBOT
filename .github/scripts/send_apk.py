#!/usr/bin/env python3
import html
import mimetypes
import os
import re
import sys
import uuid
import urllib.request
import urllib.parse
import json

def build_multipart_body(fields: dict, files: dict, boundary: str) -> bytes:
    body = bytearray()
    # Add text fields
    for key, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        body.extend(f"{value}\r\n".encode("utf-8"))

    # Add file fields
    for field_name, (file_name, file_data) in files.items():
        content_type = mimetypes.guess_type(file_name)[0] or "application/vnd.android.package-archive"
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{file_name}"\r\n'.encode("utf-8")
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        body.extend(file_data)
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    return bytes(body)

def main():
    bot_token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.environ.get("CHAT_ID") or "").strip()
    app_name = (os.environ.get("APP_NAME") or "VibeApp").strip() or "VibeApp"
    app_id = (os.environ.get("APP_ID") or "com.vibeapp.app").strip()

    if not bot_token or not chat_id:
        print("Missing TELEGRAM_BOT_TOKEN or CHAT_ID", file=sys.stderr)
        sys.exit(1)

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    apk_dir = os.path.join(project_root, "android-template", "app", "build", "outputs", "apk")
    
    apk_candidates = []
    if os.path.isdir(apk_dir):
        for root, dirs, files in os.walk(apk_dir):
            for file in files:
                if file.endswith(".apk") and not file.endswith("-androidTest.apk"):
                    apk_candidates.append(os.path.join(root, file))

    if not apk_candidates:
        print(f"No APK file found in {apk_dir}!", file=sys.stderr)
        sys.exit(1)

    apk_path = apk_candidates[0]
    file_size_mb = os.path.getsize(apk_path) / (1024 * 1024)
    print(f"Built APK found at {apk_path}! Size: {file_size_mb:.2f} MB")

    # Sanitize file name for Telegram document
    clean_name = re.sub(r'[^a-zA-Z0-9_\-\u0400-\u04FF]', '_', app_name).strip('_')
    if not clean_name:
        clean_name = "VibeApp"
    target_apk_name = f"{clean_name}.apk"

    with open(apk_path, "rb") as f:
        apk_bytes = f.read()

    safe_app_name = html.escape(app_name)
    safe_app_id = html.escape(app_id)

    caption = (
        f"🎉 <b>Твое приложение успешно собрано!</b>\n\n"
        f"📱 Название: <b>{safe_app_name}</b>\n"
        f"📦 Package ID: <code>{safe_app_id}</code>\n"
        f"💾 Размер: <code>{file_size_mb:.2f} MB</code>\n\n"
        f"🚀 <i>Установи APK на Android-смартфон и запускай в один клик.</i>"
    )

    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    fields = {
        "chat_id": chat_id,
        "caption": caption,
        "parse_mode": "HTML"
    }
    files = {
        "document": (target_apk_name, apk_bytes)
    }

    body = build_multipart_body(fields, files, boundary)

    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )

    print("Uploading APK to Telegram...")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            if resp_data.get("ok"):
                print("APK successfully sent to user!")
            else:
                print(f"Telegram API error: {resp_data}", file=sys.stderr)
                sys.exit(1)
    except Exception as e:
        print(f"Failed to upload APK to Telegram: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
