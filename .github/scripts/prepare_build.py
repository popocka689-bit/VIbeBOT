#!/usr/bin/env python3
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile

def download_file(bot_token: str, file_id: str, dest_path: str):
    print(f"Fetching file path from Telegram for file_id={file_id}...")
    get_file_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
    req = urllib.request.Request(get_file_url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if not data.get("ok"):
        raise RuntimeError(f"Telegram getFile failed: {data}")

    file_path = data["result"]["file_path"]
    download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
    print(f"Downloading file from {download_url}...")

    urllib.request.urlretrieve(download_url, dest_path)
    print(f"Downloaded to {dest_path} (size: {os.path.getsize(dest_path)} bytes)")

def escape_android_xml_string(val: str) -> str:
    # Android XML strings require escaping & < > " ' and leading @ / ?
    res = val.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    res = res.replace("\"", "\\\"").replace("'", "\\'")
    if res.startswith("@") or res.startswith("?"):
        res = "\\" + res
    return res

def find_web_root(extracted_dir: str) -> str:
    # First check root
    if os.path.isfile(os.path.join(extracted_dir, "index.html")):
        return extracted_dir

    # Search for index.html in subdirectories, prioritizing shallowest
    candidates = []
    for root, dirs, files in os.walk(extracted_dir):
        if "index.html" in files:
            depth = root.count(os.sep)
            candidates.append((depth, root))

    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    raise FileNotFoundError("Could not find 'index.html' inside the provided archive.")

def main():
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    file_id = os.environ.get("FILE_ID")
    app_name = os.environ.get("APP_NAME", "VibeApp").strip() or "VibeApp"
    app_id = os.environ.get("APP_ID", "").strip()

    if not bot_token or not file_id:
        print("Missing TELEGRAM_BOT_TOKEN or FILE_ID", file=sys.stderr)
        sys.exit(1)

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    template_dir = os.path.join(project_root, "android-template")
    assets_www_dir = os.path.join(template_dir, "app", "src", "main", "assets", "www")
    strings_xml_path = os.path.join(template_dir, "app", "src", "main", "res", "values", "strings.xml")
    build_gradle_path = os.path.join(template_dir, "app", "build.gradle")

    print(f"Target assets directory: {assets_www_dir}")
    os.makedirs(assets_www_dir, exist_ok=True)

    # 1. Download file
    with tempfile.TemporaryDirectory() as tmp_dir:
        downloaded_file = os.path.join(tmp_dir, "input_asset")
        download_file(bot_token, file_id, downloaded_file)

        # 2. Check if file is ZIP
        is_zip = False
        try:
            if zipfile.is_zipfile(downloaded_file):
                is_zip = True
        except Exception:
            is_zip = False

        # Clear existing assets in www
        for item in os.listdir(assets_www_dir):
            item_path = os.path.join(assets_www_dir, item)
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.unlink(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)

        if is_zip:
            print("Detected ZIP archive. Extracting...")
            extract_folder = os.path.join(tmp_dir, "extracted")
            os.makedirs(extract_folder, exist_ok=True)
            with zipfile.ZipFile(downloaded_file, 'r') as zf:
                zf.extractall(extract_folder)

            web_root = find_web_root(extract_folder)
            print(f"Found web root directory: {web_root}")

            # Copy all files from web_root to assets_www_dir
            for item in os.listdir(web_root):
                src_item = os.path.join(web_root, item)
                dst_item = os.path.join(assets_www_dir, item)
                if os.path.isdir(src_item):
                    shutil.copytree(src_item, dst_item)
                else:
                    shutil.copy2(src_item, dst_item)
        else:
            print("Treating file as standalone index.html...")
            # If user sent an HTML file or raw HTML
            dst_index = os.path.join(assets_www_dir, "index.html")
            shutil.copy2(downloaded_file, dst_index)

    # 3. Update strings.xml (app_name)
    print(f"Updating app_name to: '{app_name}'")
    escaped_app_name = escape_android_xml_string(app_name)
    with open(strings_xml_path, "r", encoding="utf-8") as f:
        strings_content = f.read()

    new_strings_content = re.sub(
        r'<string name="app_name">.*?</string>',
        f'<string name="app_name">{escaped_app_name}</string>',
        strings_content
    )
    with open(strings_xml_path, "w", encoding="utf-8") as f:
        f.write(new_strings_content)

    # 4. Update build.gradle (applicationId)
    if app_id:
        # Validate package name syntax (e.g. com.vibeapp.u123.t456)
        clean_app_id = re.sub(r'[^a-zA-Z0-9_\.]', '', app_id)
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$', clean_app_id):
            clean_app_id = "com.vibeapp.app"
        print(f"Updating applicationId to: '{clean_app_id}'")
        with open(build_gradle_path, "r", encoding="utf-8") as f:
            gradle_content = f.read()

        new_gradle_content = re.sub(
            r'applicationId\s+"[^"]+"',
            f'applicationId "{clean_app_id}"',
            gradle_content
        )
        with open(build_gradle_path, "w", encoding="utf-8") as f:
            f.write(new_gradle_content)

    print("Project prepared successfully for compilation!")

if __name__ == "__main__":
    main()
