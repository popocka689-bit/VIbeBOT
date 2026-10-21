# ⚡ VibeAPK Builder

Облачный сервис и Telegram-бот для автоматической компиляции HTML/CSS/JS веб-приложений в автономные нативные Android APK без необходимости коммитить пользовательские файлы в репозиторий (**Zero-Commit Build**).

---

## 🏛 Архитектура

```
[Пользователь]
      │  .zip / .html / HTML-текст + Имя приложения
      ▼
[Telegram Bot (aiogram 3.x)]
      │  workflow_dispatch (chat_id, file_id, app_name, app_id)
      ▼
[GitHub Actions Runner (Ubuntu)]
      │  1. Скачивает файл по file_id через Bot API
      │  2. Распаковывает в android-template/app/src/main/assets/www
      │  3. Подставляет уникальный package ID и strings.xml
      │  4. Компилирует APK через Gradle 8 & Android SDK 34
      ▼
[Telegram Bot API: sendDocument]
      │  Готовый <AppName>.apk с прямой доставкой в чат
      ▼
[Пользователь] (Установка на Android в 1 клик)
```

---

## 🚀 Быстрый старт

### 1. Настройка GitHub репозитория
1. Создайте **новый репозиторий** на GitHub (например, `vibe-apk-builder`).
2. В репозитории откройте **Settings -> Secrets and variables -> Actions** и добавьте Secret:
   - `TELEGRAM_BOT_TOKEN`: токен вашего бота от `@BotFather`.
3. В **Settings -> Actions -> General -> Workflow permissions**:
   - Убедитесь, что выбрано **Read and write permissions** (для работы воркфлоу).

### 2. Получение GitHub Personal Access Token (PAT)
Бот использует GitHub REST API для запуска воркфлоу:
1. Перейдите в [GitHub Personal Access Tokens](https://github.com/settings/tokens).
2. Выберите **Generate new token (classic)**.
3. Отметьте scope: `repo` (или `workflow`).
4. Скопируйте созданный токен (начинается на `ghp_...`).

### 3. Загрузка кода в ваш репозиторий
Выполните в терминале проекта:
```bash
git init
git add .
git commit -m "feat: initial commit VibeAPK Builder"
git branch -M main
git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/<YOUR_REPO_NAME>.git
git push -u origin main
```

### 4. Настройка и запуск Telegram-бота
Перейдите в папку бота:
```bash
cd bot
cp .env.example .env
```
Заполните `.env`:
```env
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
GITHUB_TOKEN=ghp_yourPersonalAccessTokenHere
GITHUB_REPO=your-github-username/vibe-apk-builder
GITHUB_WORKFLOW_ID=build_apk.yml
GITHUB_BRANCH=main
```

Установите зависимости и запустите бота:
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python main.py

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

---

## 📱 Особенности Android WebView шаблона (`/android-template`)
- **WebViewAssetLoader**: Локальные файлы загружаются по виртуальному защищенному URL `https://appassets.androidplatform.net/assets/www/index.html`. Это полностью устраняет ограничения CORS, работу с ES6 `import`/`export` и `fetch()`.
- **LocalStorage & IndexedDB**: `domStorageEnabled = true` и `databaseEnabled = true`.
- **Поддержка нативных диалогов**: `WebChromeClient` перехватывает `alert()`, `confirm()` и перенаправляет `console.log` в Android Logcat.
- **Аппаратная кнопка «Назад»**: Управляется через `OnBackPressedCallback` с возвратом по истории переходов в браузере.
- **Уникальный Package ID**: Для каждой сборки генерируется уникальный `applicationId` вида `com.vibeapp.u<chat_id>.t<timestamp>`, поэтому на одном смартфоне можно держать десятки разных веб-приложений без конфликтов.
