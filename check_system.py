#!/usr/bin/env python3

import sys
import os

print("=" * 60)
print("ПРОВЕРКА КОМПОНЕНТОВ RESUME BUILDER BOT")
print("=" * 60)

print("\n1. Проверка Python...")
print(f"   Python версия: {sys.version}")
if sys.version_info >= (3, 11):
    print("   Python 3.11+ OK")
else:
    print("   Рекомендуется Python 3.11+")

print("\n2. Проверка зависимостей...")
required_packages = {
    'telegram': 'python-telegram-bot',
    'gspread': 'gspread',
    'oauth2client': 'oauth2client',
    'dotenv': 'python-dotenv',
    'google.generativeai': 'google-generativeai'
}

missing = []
for module, package in required_packages.items():
    try:
        __import__(module if '.' not in module else module.split('.')[0])
        print(f"   {package}")
    except ImportError:
        print(f"   {package} - ОТСУТСТВУЕТ")
        missing.append(package)

if missing:
    print(f"\n   Установи отсутствующие пакеты:")
    print(f"   pip install {' '.join(missing)}")

print("\n3. Проверка LaTeX...")
import subprocess
try:
    result = subprocess.run(['pdflatex', '--version'], 
                          capture_output=True, timeout=5)
    if result.returncode == 0:
        version = result.stdout.decode().split('\n')[0]
        print(f"   pdflatex установлен: {version}")
    else:
        print("   pdflatex НЕ работает")
except FileNotFoundError:
    print("   pdflatex НЕ УСТАНОВЛЕН")
    print("   PDF генерация недоступна - будут создаваться .tex файлы")
    print("   Установка:")
    print("   - Ubuntu: sudo apt-get install texlive-latex-base texlive-fonts-recommended texlive-fonts-extra texlive-latex-extra texlive-lang-cyrillic")
    print("   - Mac: brew install --cask mactex")
    print("   - Windows: скачай MiKTeX с miktex.org")
except subprocess.TimeoutExpired:
    print("   pdflatex timeout")

print("\n4. Проверка environment variables...")
from dotenv import load_dotenv
load_dotenv()

env_vars = {
    'TELEGRAM_TOKEN': 'Токен Telegram бота',
    'SPREADSHEET_ID': 'ID Google таблицы',
    'GOOGLE_API_KEY': 'API ключ Google Gemini (опционально)',
}

all_set = True
for var, desc in env_vars.items():
    value = os.getenv(var)
    if value:
        masked = value[:10] + '...' if len(value) > 10 else value
        print(f"   {var}: {masked}")
    else:
        print(f"   {var}: НЕ УСТАНОВЛЕНА ({desc})")
        all_set = False

if os.path.exists('credentials.json'):
    print(f"   credentials.json: найден")
elif os.getenv('GOOGLE_CREDENTIALS_JSON'):
    print(f"   GOOGLE_CREDENTIALS_JSON: установлена")
else:
    print(f"   credentials.json: НЕ НАЙДЕН")
    all_set = False

if not all_set:
    print("\n   Создай .env файл на основе .env.example")

print("\n5. Проверка файлов проекта...")
required_files = [
    'bot.py', 'config.py', 'database.py', 
    'ai_analyzer.py', 'latex_generator.py', 'keyboards.py'
]

for file in required_files:
    if os.path.exists(file):
        size = os.path.getsize(file)
        print(f"   {file} ({size} bytes)")
    else:
        print(f"   {file} - ОТСУТСТВУЕТ")

print("\n6. Тест Google Sheets API...")
try:
    import config
    from database import Database
    
    db = Database()
    print("   Подключение к Google Sheets успешно")
    try:
        sheet_title = db.spreadsheet.title
        print(f"   Таблица: {sheet_title}")
        worksheets = [ws.title for ws in db.spreadsheet.worksheets()]
        print(f"   Листы: {', '.join(worksheets)}")
    except Exception as e:
        print(f"   Ошибка чтения таблицы: {e}")
        
except Exception as e:
    print(f"   Ошибка подключения: {e}")
    print("   Проверь credentials.json и SPREADSHEET_ID")

print("\n7. Тест Google Gemini API...")
try:
    import google.generativeai as genai
    import config
    
    if config.GOOGLE_API_KEY:
        genai.configure(api_key=config.GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        response = model.generate_content("Say 'OK' if you work")
        if response.text:
            print(f"   Gemini API работает: {response.text[:50]}")
        else:
            print("   Gemini API не отвечает")
    else:
        print("   GOOGLE_API_KEY не установлен - будет использован fallback")
        
except ImportError:
    print("   google-generativeai не установлен - будет использован fallback")
except Exception as e:
    print(f"   Ошибка Gemini API: {e}")
    print("   Будет использован fallback анализ (regex)")

print("\n" + "=" * 60)
print("📊 ИТОГОВЫЙ СТАТУС")
print("=" * 60)

if not missing and all_set:
    print("ВСЕ КОМПОНЕНТЫ ГОТОВЫ К РАБОТЕ!")
    print("\nЗапусти бота: python bot.py")
else:
    print("ТРЕБУЕТСЯ НАСТРОЙКА")
    if missing:
        print(f"\n1. Установи зависимости: pip install {' '.join(missing)}")
    if not all_set:
        print("2. Настрой .env файл (см. .env.example)")
    print("\n После этого запусти: python bot.py")

print("\nПодробнее см. README.md")
print("=" * 60)
