#!/usr/bin/env bash
echo "Installing LaTeX..."

apt-get update
apt-get install -y texlive-latex-base texlive-fonts-recommended texlive-fonts-extra texlive-latex-extra texlive-lang-cyrillic

echo "LaTeX installed"
echo "Starting bot..."

python bot.py
