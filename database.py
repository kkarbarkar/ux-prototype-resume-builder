import gspread
from datetime import datetime
import config
import os
import json
import time
from oauth2client.service_account import ServiceAccountCredentials

class Database:
    USERS_HEADERS = [
        'UserID', 'Username', 'Дата регистрации', 'ФИО', 'Email', 'Телефон',
        'Город', 'LinkedIn', 'GitHub', 'Portfolio',
        'Университет', 'Специальность', 'Период обучения',
        'Образование (JSON)',
        'Опыт работы (JSON)', 'Проекты (JSON)', 'Технические навыки',
        'Soft skills', 'Достижения', 'Языки', 'Интересы',
        'Текст вакансии', 'Ключевые слова (JSON)', 'Выбранный шаблон',
        'Дата создания резюме', 'Статус', 'Feedback (JSON)'
    ]
    FEEDBACK_HEADERS = [
        'UserID', 'Username', 'Дата', 'Оценка резюме', 'Будет использовать',
        'Время редактирования', 'Редактировал резюме', 'Общая оценка',
        'Комментарий', 'Статус конверсии'
    ]

    def __init__(self):
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')

        if creds_json:
            info = json.loads(creds_json)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scope)
        else:
            # Если переменной нет, ищем файл (для тестов на компе)
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                config.CREDENTIALS_FILE, scope
            )

        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(config.SPREADSHEET_ID)
        self._init_sheets()


    def _init_sheets(self):
        """Инициализация листов"""
        try:
            self.users_sheet = self.spreadsheet.worksheet('Users')
        except:
            self.users_sheet = self.spreadsheet.add_worksheet(
                title='Users', rows=1000, cols=30
            )
            # ИСПРАВЛЕНИЕ: правильные заголовки
            self.users_sheet.append_row(self.USERS_HEADERS)

        try:
            self.feedback_sheet = self.spreadsheet.worksheet('Feedback')
        except:
            self.feedback_sheet = self.spreadsheet.add_worksheet(
                title='Feedback', rows=1000, cols=15
            )
            self.feedback_sheet.append_row(self.FEEDBACK_HEADERS)

        try:
            self.analytics_sheet = self.spreadsheet.worksheet('Analytics')
        except:
            self.analytics_sheet = self.spreadsheet.add_worksheet(
                title='Analytics', rows=1000, cols=10
            )
            headers = [
                'Дата', 'Всего пользователей', 'Завершили резюме',
                'Конверсия %', 'Средняя оценка', 'Используют резюме',
                'Время редактирования <30 мин', 'Редактировали'
            ]
            self.analytics_sheet.append_row(headers)

    def _dedupe_headers(self, headers):
        seen = {}
        result = []
        for h in headers:
            name = h if h else 'Column'
            if name in seen:
                seen[name] += 1
                result.append(f"{name}_{seen[name]}")
            else:
                seen[name] = 1
                result.append(name)
        return result

    def _get_all_records(self, sheet, expected_headers):
        try:
            return sheet.get_all_records(expected_headers=expected_headers)
        except Exception:
            values = sheet.get_all_values()
            if not values:
                return []
            headers = values[0]
            if expected_headers and len(expected_headers) == len(headers):
                headers = expected_headers
            else:
                headers = self._dedupe_headers(headers)
            records = []
            for row in values[1:]:
                if len(row) < len(headers):
                    row = row + [''] * (len(headers) - len(row))
                records.append(dict(zip(headers, row[:len(headers)])))
            return records

    def _column_letter(self, index):
        """1-based column index to A1 letter notation."""
        letters = ""
        while index > 0:
            index, rem = divmod(index - 1, 26)
            letters = chr(65 + rem) + letters
        return letters

    def save_user_data(self, user_id, username, data):
        """Сохранение данных пользователя"""
        # Сериализуем сложные структуры
        experiences_json = json.dumps(data.get('experiences', []), ensure_ascii=False)
        projects_json = json.dumps(data.get('projects', []), ensure_ascii=False)
        educations_json = json.dumps(data.get('educations', []), ensure_ascii=False)
        keywords_json = json.dumps(data.get('vacancy_keywords', {}), ensure_ascii=False)
        feedback_json = json.dumps(data.get('feedback', {}), ensure_ascii=False)

        row_data = [
            user_id,
            username or '',
            data.get('registration_date', datetime.now().strftime('%Y-%m-%d %H:%M')),
            data.get('full_name', ''),
            data.get('email', ''),
            data.get('phone', ''),
            data.get('location', ''),
            data.get('linkedin', ''),
            data.get('github', ''),
            data.get('portfolio', ''),
            data.get('university', ''),
            data.get('degree', ''),
            data.get('study_period', ''),
            educations_json,
            experiences_json,
            projects_json,
            data.get('technical_skills', ''),
            data.get('soft_skills', ''),
            data.get('achievements', ''),
            data.get('languages', ''),
            data.get('interests', ''),
            data.get('vacancy_text', ''),
            keywords_json,
            data.get('template', ''),
            data.get('resume_date', ''),
            data.get('status', 'in_progress'),
            feedback_json
        ]

        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                cell = self.users_sheet.find(str(user_id))
                if cell:
                    row_num = cell.row
                    end_col = self._column_letter(len(row_data))
                    self.users_sheet.update(f"A{row_num}:{end_col}{row_num}", [row_data])
                else:
                    self.users_sheet.append_row(row_data)
                return True
            except Exception as e:
                print(f"Error saving user data (attempt {attempt}/{attempts}): {e}")
                if attempt < attempts:
                    time.sleep(0.6 * attempt)
                else:
                    return False

    def get_user_data(self, user_id):
        """Получение данных пользователя"""
        try:
            cell = self.users_sheet.find(str(user_id))
            if cell:
                row = self.users_sheet.row_values(cell.row)
                headers = self.users_sheet.row_values(1)

                data = dict(zip(headers, row))

                # Десериализуем JSON
                if 'Опыт работы (JSON)' in data and data['Опыт работы (JSON)']:
                    try:
                        data['experiences'] = json.loads(data['Опыт работы (JSON)'])
                    except:
                        data['experiences'] = []

                if 'Образование (JSON)' in data and data['Образование (JSON)']:
                    try:
                        data['educations'] = json.loads(data['Образование (JSON)'])
                    except:
                        data['educations'] = []
                elif data.get('Университет') or data.get('Специальность') or data.get('Период обучения'):
                    data['educations'] = [{
                        'university': data.get('Университет', ''),
                        'degree': data.get('Специальность', ''),
                        'study_period': data.get('Период обучения', '')
                    }]

                if 'Проекты (JSON)' in data and data['Проекты (JSON)']:
                    try:
                        data['projects'] = json.loads(data['Проекты (JSON)'])
                    except:
                        data['projects'] = []

                if 'Ключевые слова (JSON)' in data and data['Ключевые слова (JSON)']:
                    try:
                        data['vacancy_keywords'] = json.loads(data['Ключевые слова (JSON)'])
                    except:
                        data['vacancy_keywords'] = {}

                return data
            return None
        except Exception as e:
            print(f"Error getting user data: {e}")
            return None

    def save_feedback(self, user_id, username, feedback_data):
        """Сохранение обратной связи"""
        try:
            row_data = [
                user_id,
                username or '',
                datetime.now().strftime('%Y-%m-%d %H:%M'),
                feedback_data.get('resume_rating', ''),
                feedback_data.get('will_use', ''),
                feedback_data.get('editing_time', ''),
                feedback_data.get('did_edit', ''),
                feedback_data.get('overall_experience', ''),
                feedback_data.get('comment', ''),
                feedback_data.get('conversion_status', 'completed')
            ]
            self.feedback_sheet.append_row(row_data)

            # Также сохраняем в основную таблицу
            user_data = self.get_user_data(user_id)
            if user_data:
                user_data['feedback'] = feedback_data
                self.save_user_data(user_id, username, user_data)

            return True
        except Exception as e:
            print(f"Error saving feedback: {e}")
            return False

    def update_analytics(self):
        """Обновление аналитики"""
        try:
            all_users = self._get_all_records(self.users_sheet, self.USERS_HEADERS)

            total_users = len(all_users)
            completed = len([u for u in all_users if u.get('Статус') == 'completed'])
            conversion = (completed / total_users * 100) if total_users > 0 else 0

            # Получаем feedback
            all_feedback = self._get_all_records(self.feedback_sheet, self.FEEDBACK_HEADERS)

            # Исправление: проверяем тип данных
            ratings = []
            for f in all_feedback:
                rating_val = f.get('Оценка резюме', '')
                if isinstance(rating_val, (int, float)):
                    ratings.append(int(rating_val))
                elif isinstance(rating_val, str) and rating_val.isdigit():
                    ratings.append(int(rating_val))

            avg_rating = sum(ratings) / len(ratings) if ratings else 0

            will_use = len([f for f in all_feedback if f.get('Будет использовать') == 'Да'])
            edited = len([f for f in all_feedback if f.get('Редактировал резюме') == 'Да'])
            quick_edit = len([f for f in all_feedback if '15' in str(f.get('Время редактирования', ''))])

            row_data = [
                datetime.now().strftime('%Y-%m-%d'),
                total_users,
                completed,
                f"{conversion:.1f}%",
                f"{avg_rating:.1f}",
                will_use,
                quick_edit,
                edited
            ]

            self.analytics_sheet.append_row(row_data)
            return True
        except Exception as e:
            print(f"Error updating analytics: {e}")
            return False
