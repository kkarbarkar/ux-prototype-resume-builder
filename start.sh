#!/usr/bin/env bash
# Render startup script - установка LaTeX и запуск бота

echo "🔧 Installing LaTeX..."

# Обновляем apt и устанавливаем texlive
apt-get update
apt-get install -y texlive-latex-base texlive-fonts-recommended texlive-fonts-extra texlive-latex-extra texlive-lang-cyrillic

echo "✅ LaTeX installed"
echo "🚀 Starting bot..."

# Запускаем бота
python bot.py
