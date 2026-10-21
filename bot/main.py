import asyncio
import logging
import os
import re
import sys
import time
from typing import Optional

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "").strip()
GITHUB_WORKFLOW_ID = os.getenv("GITHUB_WORKFLOW_ID", "build_apk.yml").strip()
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()
PORT = int(os.getenv("PORT", "8080"))

# Telegram Bot API limit for getFile/download
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("VibeAPKBot")


class BuildStates(StatesGroup):
    waiting_for_input = State()
    waiting_for_app_name = State()
    waiting_for_icon = State()


def get_default_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚡ Использовать имя: VibeApp",
                    callback_data="use_default_name"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="cancel_action"
                )
            ]
        ]
    )


def get_icon_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⏩ Пропустить (стандартная иконка)",
                    callback_data="skip_icon"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="cancel_action"
                )
            ]
        ]
    )


async def dispatch_github_workflow(
    chat_id: int,
    file_id: str,
    app_name: str,
    app_id: str,
    icon_file_id: str = ""
) -> tuple[bool, str]:
    """Triggers GitHub Actions workflow_dispatch via REST API."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False, "GITHUB_TOKEN или GITHUB_REPO не настроены в .env файле сервера."

    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW_ID}/dispatches"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "VibeAPK-Builder-Bot"
    }
    payload = {
        "ref": GITHUB_BRANCH,
        "inputs": {
            "chat_id": str(chat_id),
            "file_id": file_id,
            "icon_file_id": icon_file_id,
            "app_name": app_name,
            "app_id": app_id
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=20) as resp:
                if resp.status == 204:
                    return True, "Успешно отправлено в очередь сборки GitHub Actions."
                else:
                    body = await resp.text()
                    logger.error("GitHub API returned status %s: %s", resp.status, body)
                    if resp.status == 404:
                        return False, (
                            f"GitHub вернул 404. Проверь имя репозитория ({GITHUB_REPO}) "
                            f"или имя воркфлоу ({GITHUB_WORKFLOW_ID})."
                        )
                    elif resp.status in (401, 403):
                        return False, (
                            "Ошибка авторизации в GitHub API. Проверь права GITHUB_TOKEN "
                            "(нужен scope 'repo' или 'Actions: Read and write')."
                        )
                    return False, f"Ошибка GitHub API ({resp.status}): {body[:150]}"
    except Exception as e:
        logger.exception("Error while requesting GitHub Actions API")
        return False, f"Сетевая ошибка при обращении к GitHub: {str(e)}"


# Bot instance and Dispatcher
dp = Dispatcher(storage=MemoryStorage())


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    welcome_text = (
        "👋 <b>Привет! Я VibeAPK Builder</b> — облачный компилятор веб-приложений в автономные Android APK!\n\n"
        "📦 <b>Как это работает (Zero-Commit Build):</b>\n"
        "1. Отправь мне свой веб-проект:\n"
        "   • <b>.zip архив</b> с <code>index.html</code> и ресурсами (css, js, картинки).\n"
        "   • <b>.html файл</b> (одностраничник).\n"
        "   • Или просто <b>текст с HTML-кодом</b> прямо в чат!\n"
        "2. Укажи название приложения.\n"
        "3. Облачный раннер GitHub Actions скомпилирует APK и бот пришлет готовый файл прямо сюда!\n\n"
        "⚡ <i>Отправь файл прямо сейчас, чтобы начать:</i>"
    )
    await message.answer(welcome_text, parse_mode="HTML")
    await state.set_state(BuildStates.waiting_for_input)


@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "📖 <b>Инструкция по подготовке архива:</b>\n\n"
        "• В корне вашего <code>.zip</code> архива должен находиться <code>index.html</code> "
        "(даже если архив содержит вложенную папку, наш сборщик автоматически её распакует).\n"
        "• Приложение работает через <b>WebViewAssetLoader</b>, поэтому все относительные пути "
        "(<code>./style.css</code>, <code>js/main.js</code>) и fetch-запросы работают без ошибок CORS.\n"
        "• Включены: LocalStorage, WebChromeClient (диалоги и консоль), аппаратная кнопка «Назад».\n\n"
        "Для сброса текущего шага введи команду /cancel."
    )
    await message.answer(help_text, parse_mode="HTML")


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🔄 Действие отменено. Отправь новый .zip, .html или HTML-текст для сборки.")
    await state.set_state(BuildStates.waiting_for_input)


@dp.callback_query(F.data == "cancel_action")
async def cb_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🔄 Сборка отменена. Отправь новый файл, когда будешь готов.")
    await state.set_state(BuildStates.waiting_for_input)
    await callback.answer()


@dp.message(F.document)
async def handle_document(message: Message, state: FSMContext):
    doc = message.document
    file_name = (doc.file_name or "").lower()

    if not (file_name.endswith(".zip") or file_name.endswith(".html") or file_name.endswith(".htm")):
        await message.reply(
            "⚠️ Пожалуйста, отправь файл формата <b>.zip</b> (архив проекта) "
            "или <b>.html</b> (веб-страница).",
            parse_mode="HTML"
        )
        return

    if doc.file_size and doc.file_size > MAX_FILE_SIZE_BYTES:
        mb_size = doc.file_size / (1024 * 1024)
        await message.reply(
            f"❌ Размер файла слишком большой ({mb_size:.1f} МБ). "
            f"Лимит Telegram Bot API — до 20 МБ.",
            parse_mode="HTML"
        )
        return

    # Store file_id and filename in state
    await state.update_data(
        file_id=doc.file_id,
        file_name=doc.file_name or "app.zip"
    )
    await state.set_state(BuildStates.waiting_for_app_name)

    suggested_name = "VibeApp"
    if doc.file_name:
        base = doc.file_name.rsplit(".", 1)[0]
        cleaned = re.sub(r'[^a-zA-Z0-9_\-\s]', '', base).strip()
        if cleaned:
            suggested_name = cleaned[:30]

    await message.reply(
        f"✅ Файл <code>{doc.file_name}</code> принят!\n\n"
        f"🎯 <b>Введи имя приложения</b> (оно будет отображаться на экране смартфона под иконкой):\n"
        f"Или нажми кнопку ниже для быстрого старта.",
        parse_mode="HTML",
        reply_markup=get_default_keyboard()
    )


@dp.message(F.text)
async def handle_text(message: Message, state: FSMContext):
    current_state = await state.get_state()

    # If we are waiting for the app name
    if current_state == BuildStates.waiting_for_app_name.state:
        app_name = message.text.strip()
        if len(app_name) > 40:
            app_name = app_name[:40]
        await ask_for_icon(message, state, app_name)
        return

    # Check if text looks like HTML code
    text = message.text.strip()
    looks_like_html = (
        "<html" in text.lower() or
        "<!doctype" in text.lower() or
        "<div" in text.lower() or
        "<script" in text.lower() or
        ("<" in text and ">" in text and len(text) > 20)
    )

    if looks_like_html:
        processing_msg = await message.reply("⏳ Оборачиваю ваш HTML-код в <code>index.html</code>...", parse_mode="HTML")
        file_bytes = text.encode("utf-8")
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            await processing_msg.edit_text("❌ Размер HTML-кода превышает 20 МБ.")
            return

        # Upload as document to obtain a Telegram file_id
        uploaded = await message.answer_document(
            document=BufferedInputFile(file_bytes, filename="index.html"),
            caption="📄 HTML-файл сформирован для сборки."
        )

        await state.update_data(
            file_id=uploaded.document.file_id,
            file_name="index.html"
        )
        await state.set_state(BuildStates.waiting_for_app_name)

        await message.answer(
            "🎯 <b>Введи название для приложения</b> (или выбери кнопку ниже):",
            parse_mode="HTML",
            reply_markup=get_default_keyboard()
        )
    else:
        await message.reply(
            "💡 Чтобы начать сборку APK, отправь мне <b>.zip</b> архив проекта, "
            "<b>.html</b> файл или <b>HTML-код</b> прямо сообщением.\n\n"
            "Справка: /help",
            parse_mode="HTML"
        )


@dp.callback_query(F.data == "use_default_name")
async def cb_use_default_name(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    file_name = data.get("file_name", "VibeApp")
    default_name = file_name.rsplit(".", 1)[0].replace("_", " ").title()
    default_name = re.sub(r'[^a-zA-Z0-9_\-\s]', '', default_name).strip() or "VibeApp"
    await ask_for_icon(callback.message, state, default_name)


async def ask_for_icon(message: Message, state: FSMContext, app_name: str):
    await state.update_data(app_name=app_name)
    await state.set_state(BuildStates.waiting_for_icon)
    await message.answer(
        f"🎯 Имя приложения: <b>{app_name}</b>\n\n"
        f"🖼 <b>Шаг 2/2: Логотип приложения (иконка)</b>\n\n"
        f"Отправь <b>фото или картинку</b> (PNG/JPG), чтобы сделать её иконкой на экране смартфона!\n\n"
        f"<i>Или нажми кнопку ниже, чтобы использовать стандартную иконку VibeApp:</i>",
        parse_mode="HTML",
        reply_markup=get_icon_keyboard()
    )


@dp.message(BuildStates.waiting_for_icon, F.photo)
async def handle_icon_photo(message: Message, state: FSMContext):
    photo_file_id = message.photo[-1].file_id
    await process_build_request(message, state, icon_file_id=photo_file_id)


@dp.message(BuildStates.waiting_for_icon, F.document)
async def handle_icon_document(message: Message, state: FSMContext):
    doc = message.document
    mime = (doc.mime_type or "").lower()
    fname = (doc.file_name or "").lower()
    if mime.startswith("image/") or fname.endswith((".png", ".jpg", ".jpeg", ".webp")):
        await process_build_request(message, state, icon_file_id=doc.file_id)
    else:
        await message.reply(
            "⚠️ Пожалуйста, отправь картинку (PNG или JPG) или нажми кнопку «Пропустить».",
            reply_markup=get_icon_keyboard()
        )


@dp.callback_query(BuildStates.waiting_for_icon, F.data == "skip_icon")
async def cb_skip_icon(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await process_build_request(callback.message, state, icon_file_id="")


@dp.message(BuildStates.waiting_for_icon, Command("skip"))
async def cmd_skip_icon(message: Message, state: FSMContext):
    await process_build_request(message, state, icon_file_id="")


async def process_build_request(
    message: Message,
    state: FSMContext,
    icon_file_id: str = ""
):
    data = await state.get_data()
    file_id = data.get("file_id")
    app_name = data.get("app_name", "VibeApp")

    if not file_id:
        await message.answer("⚠️ Файл не найден в сессии. Пожалуйста, отправь файл заново.")
        await state.set_state(BuildStates.waiting_for_input)
        return

    chat_id = message.chat.id
    timestamp = int(time.time())
    # Generate unique, collision-free Android package ID
    app_id = f"com.vibeapp.u{abs(chat_id)}.t{timestamp}"

    icon_status = "Кастомная 🎨" if icon_file_id else "Стандартная ⚡"

    status_msg = await message.answer(
        f"🚀 <b>Инициирую облачную сборку...</b>\n\n"
        f"📱 Название: <b>{app_name}</b>\n"
        f"🖼 Иконка: <b>{icon_status}</b>\n"
        f"📦 Package ID: <code>{app_id}</code>\n"
        f"🌐 Передаю параметры в GitHub Actions...",
        parse_mode="HTML"
    )

    success, reply_text = await dispatch_github_workflow(
        chat_id=chat_id,
        file_id=file_id,
        app_name=app_name,
        app_id=app_id,
        icon_file_id=icon_file_id
    )

    if success:
        await status_msg.edit_text(
            f"✅ <b>Сборка успешно запущена в облаке GitHub Actions!</b>\n\n"
            f"📱 Приложение: <b>{app_name}</b>\n"
            f"📦 Package ID: <code>{app_id}</code>\n\n"
            f"⏳ <i>Сейчас сервер разворачивает Android SDK, компилирует WebView и упакует APK. "
            f"Как только сборка завершится (~1-2 мин), бот пришлет готовый .apk файл в этот чат.</i>",
            parse_mode="HTML"
        )
    else:
        await status_msg.edit_text(
            f"❌ <b>Не удалось запустить сборку в GitHub Actions:</b>\n\n{reply_text}",
            parse_mode="HTML"
        )

    # Clear state so user can immediately build another app
    await state.clear()
    await state.set_state(BuildStates.waiting_for_input)


async def health_check_handler(request: web.Request) -> web.Response:
    """HTTP Health-check endpoint for Render / PaaS hosting."""
    return web.Response(text="Bot is alive", status=200, content_type="text/plain")


async def start_web_server(port: int) -> web.AppRunner:
    """Starts lightweight HTTP health-check server on aiohttp."""
    app = web.Application()
    app.router.add_get("/", health_check_handler)
    app.router.add_get("/healthz", health_check_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    logger.info("HTTP Healthcheck server successfully started on http://0.0.0.0:%d", port)
    return runner


async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is missing! Please configure bot/.env file.")
        print("\n[ERROR] Переменная BOT_TOKEN не задана в файле bot/.env!")
        print("Создайте bot/.env из bot/.env.example и укажите токен вашего бота.\n")
        sys.exit(1)

    runner = await start_web_server(PORT)
    bot = Bot(token=BOT_TOKEN)
    logger.info("Starting VibeAPK Builder Telegram Bot...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
