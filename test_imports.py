#!/usr/bin/env python3
# -*- coding: utf-8 -*-

print("Testing imports...")

try:
    from telegram import Update
    print("✅ telegram - OK")
except ImportError as e:
    print(f"❌ telegram - FAILED: {e}")

try:
    import gspread
    print("✅ gspread - OK")
except ImportError as e:
    print(f"❌ gspread - FAILED: {e}")

try:
    from oauth2client.service_account import ServiceAccountCredentials
    print("✅ oauth2client - OK")
except ImportError as e:
    print(f"❌ oauth2client - FAILED: {e}")

try:
    from dotenv import load_dotenv
    print("✅ python-dotenv - OK")
except ImportError as e:
    print(f"❌ python-dotenv - FAILED: {e}")

try:
    import google.generativeai as genai
    print("✅ google-generativeai - OK")
except ImportError as e:
    print(f"❌ google-generativeai - FAILED: {e}")

print("\nAll imports tested!")