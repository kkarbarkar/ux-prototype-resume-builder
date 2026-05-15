# UX Project

Telegram-бот для сбора данных пользователя, анализа вакансии и генерации адаптированного резюме в LaTeX/PDF. Данные пользователей и обратная связь сохраняются в Google Sheets, а для анализа текста вакансии и улучшения формулировок используется Google Gemini с fallback-логикой.

## Возможности

- пошаговый сбор личных данных, образования, опыта, проектов и навыков;
- импорт текста вакансии вручную или по ссылке;
- выделение ключевых навыков из вакансии;
- улучшение пользовательских формулировок для резюме;
- генерация LaTeX/PDF резюме;
- сохранение данных, аналитики и feedback в Google Sheets.

## Структура проекта

- `bot.py` - основной Telegram-бот и сценарии диалога;
- `config.py` - настройки, вопросы анкеты и переменные окружения;
- `database.py` - работа с Google Sheets;
- `ai_analyzer.py` - анализ вакансии и редактирование текста через Gemini/fallback;
- `latex_generator.py` - генерация LaTeX и PDF;
- `keyboards.py` - inline-клавиатуры Telegram;
- `check_system.py` - проверка окружения;
- `test_*.py` - локальные проверки интеграций;
- `Dockerfile`, `render.yaml`, `start.sh` - файлы для деплоя.

## Требования

- Python 3.11+
- Telegram Bot Token
- Google Sheets API service account
- Google Gemini API key, если нужен AI-анализ
- LaTeX (`pdflatex`) для генерации PDF

## Настройка

1. Создайте виртуальное окружение и установите зависимости:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Создайте файл `.env` в корне проекта:

```env
TELEGRAM_TOKEN=your_telegram_bot_token
ADMIN_USERNAME=your_telegram_username
SPREADSHEET_ID=your_google_spreadsheet_id
GOOGLE_API_KEY=your_google_gemini_api_key
GEMINI_MODEL=gemini-1.5-flash
```

3. Для локального запуска положите `credentials.json` service account в корень проекта.

Для деплоя вместо файла можно передать JSON через переменную окружения:

```env
GOOGLE_CREDENTIALS_JSON={"type":"service_account",...}
```

4. Проверьте окружение:

```bash
python check_system.py
```

5. Запустите бота:

```bash
python bot.py
```

## Деплой

Проект содержит `Dockerfile`, `render.yaml` и `start.sh` для запуска на Render или в Docker-окружении. При деплое задайте переменные окружения из раздела настройки и убедитесь, что Google service account имеет доступ к нужной таблице.

## Локальные файлы

В репозиторий не добавляются `.env`, `credentials.json`, виртуальные окружения, кэш Python, файлы IDE и локальные отчеты `local_funnel_*`.
