import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]

creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)

spreadsheet_id = '1xMlaql_f8FPJvNc3CFJ5jg6YiAZHMnNBMyKXnEmVv_E'
spreadsheet = client.open_by_key(spreadsheet_id)

print("✅ Подключение успешно!")
print(f"Таблица: {spreadsheet.title}")
print(f"Листы: {[sheet.title for sheet in spreadsheet.worksheets()]}")