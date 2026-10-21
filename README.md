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

