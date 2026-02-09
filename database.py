import gspread
from datetime import datetime
import config
import os
import json
from oauth2client.service_account import ServiceAccountCredentials

class Database:
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
                title='Users', rows=1000, cols=25
            )
            # ИСПРАВЛЕНИЕ: правильные заголовки
            headers = [
                'UserID', 'Username', 'Дата регистрации', 'ФИО', 'Email', 'Телефон',
                'Город', 'LinkedIn', 'GitHub', 'Portfolio',
                'Университет', 'Специальность', 'Период обучения',
                'Опыт работы (JSON)', 'Проекты (JSON)', 'Технические навыки',
                'Soft skills', 'Достижения', 'Языки', 'Интересы',
                'Текст вакансии', 'Ключевые слова (JSON)', 'Выбранный шаблон',
                'Дата создания резюме', 'Статус', 'Feedback (JSON)'
            ]
            self.users_sheet.append_row(headers)

        try:
            self.feedback_sheet = self.spreadsheet.worksheet('Feedback')
        except:
            self.feedback_sheet = self.spreadsheet.add_worksheet(
                title='Feedback', rows=1000, cols=15
            )
            headers = [
                'UserID', 'Username', 'Дата', 'Оценка резюме', 'Будет использовать',
                'Время редактирования', 'Редактировал резюме', 'Общая оценка',
                'Комментарий', 'Статус конверсии'
            ]
            self.feedback_sheet.append_row(headers)

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

    def save_user_data(self, user_id, username, data):
        """Сохранение данных пользователя"""
        try:
            cell = self.users_sheet.find(str(user_id))

            # Сериализуем сложные структуры
            experiences_json = json.dumps(data.get('experiences', []), ensure_ascii=False)
            projects_json = json.dumps(data.get('projects', []), ensure_ascii=False)
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

            if cell:
                row_num = cell.row
                for col_num, value in enumerate(row_data, start=1):
                    self.users_sheet.update_cell(row_num, col_num, value)
            else:
                self.users_sheet.append_row(row_data)

            return True
        except Exception as e:
            print(f"Error saving user data: {e}")
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
            all_users = self.users_sheet.get_all_records()

            total_users = len(all_users)
            completed = len([u for u in all_users if u.get('Статус') == 'completed'])
            conversion = (completed / total_users * 100) if total_users > 0 else 0

            # Получаем feedback
            all_feedback = self.feedback_sheet.get_all_records()

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
