import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'karbarkarrr')

SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
CREDENTIALS_FILE = 'credentials.json'
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY', '')

QUESTIONS_STRUCTURE = {
    'personal': {
        'title': '👤 Личная информация',
        'questions': [
            {
                'key': 'full_name',
                'text': '<b>Как вас зовут?</b>\n\nУкажите имя и фамилию',
                'example': 'Иван Иванов',
                'required': True
            },
            {
                'key': 'email',
                'text': '<b>📧 Ваш email</b>',
                'example': 'ivan.ivanov@example.com',
                'required': True
            },
            {
                'key': 'phone',
                'text': '<b>📱 Номер телефона</b>',
                'example': '+7 999 123-45-67',
                'required': True
            },
            {
                'key': 'location',
                'text': '<b>📍 Город проживания</b>',
                'example': 'Москва',
                'required': False
            },
            {
                'key': 'linkedin',
                'text': '<b>🔗 LinkedIn</b>\n\nЕсли есть, укажите ссылку',
                'example': 'linkedin.com/in/ivan-ivanov',
                'required': False
            },
            {
                'key': 'github',
                'text': '<b>💻 GitHub</b>\n\nЕсли есть, укажите ссылку',
                'example': 'github.com/ivan-ivanov',
                'required': False
            },
            {
                'key': 'gitlab',
                'text': '<b>💻 GitLab</b>\n\nЕсли есть, укажите ссылку',
                'example': 'gitlab.com/ivan-ivanov',
                'required': False
            },
            {
                'key': 'portfolio',
                'text': '<b>🎨 Портфолио</b>\n\nСсылка на ваше портфолио (Behance, Dribbble, личный сайт)',
                'example': 'behance.net/ivan-ivanov',
                'required': False
            }
        ]
    },
    'education': {
        'title': '🎓 Образование',
        'multiple': True,
        'questions': [
            {
                'key': 'university',
                'text': '<b>Название учебного заведения</b>',
                'example': 'НИУ ВШЭ',
                'required': True
            },
            {
                'key': 'degree',
                'text': '<b>Специальность/программа</b>',
                'example': 'Прикладная математика и информатика',
                'required': True
            },
            {
                'key': 'study_period',
                'text': '<b>Период обучения</b>',
                'example': '2019 - 2023',
                'required': True
            }
        ]
    },
    'experience': {
        'title': '💼 Опыт работы',
        'multiple': True,
        'questions': [
            {
                'key': 'position',
                'text': '<b>Должность</b>',
                'example': 'Junior Python Developer',
                'required': True
            },
            {
                'key': 'company',
                'text': '<b>Компания</b>',
                'example': 'Yandex',
                'required': True
            },
            {
                'key': 'work_period',
                'text': '<b>Период работы</b>',
                'example': 'Июнь 2022 - настоящее время',
                'required': True
            },
            {
                'key': 'responsibilities',
                'text': '<b>Обязанности и достижения</b>\n\n💡 Опишите каждый пункт с новой строки',
                'example': 'Разработал REST API с использованием FastAPI\nУвеличил производительность на 30%\nПровел code review для 15+ pull requests',
                'required': True
            },
        ]
    },
    'projects': {
        'title': '🚀 Проекты',
        'multiple': True,
        'questions': [
            {
                'key': 'project_name',
                'text': '<b>Название проекта</b>',
                'example': 'Телеграм-бот для анализа данных',
                'required': True
            },
            {
                'key': 'project_description',
                'text': '<b>Описание и результаты</b>\n\n💡 Укажите технологии и достижения (каждое с новой строки)',
                'example': 'Разработал бота на Python с использованием aiogram\nИнтегрировал pandas для анализа данных\n500+ активных пользователей',
                'required': True
            }
        ]
    },
    'skills': {
        'title': '💡 Навыки',
        'questions': [
            {
                'key': 'technical_skills',
                'text': '<b>Технические навыки</b>\n\nПеречислите через запятую: языки программирования, фреймворки, инструменты',
                'example': 'Python, JavaScript, React, PostgreSQL, Git, Docker',
                'required': True
            },
            {
                'key': 'soft_skills',
                'text': '<b>Soft skills</b>\n\nПеречислите через запятую',
                'example': 'Командная работа, Презентации, Тайм-менеджмент',
                'required': False
            }
        ]
    },
    'additional': {
        'title': '✨ Дополнительно',
        'questions': [
            {
                'key': 'achievements',
                'text': '<b>🏆 Достижения</b>\n\nНаграды, олимпиады, сертификаты (каждое с новой строки)',
                'example': 'Победитель хакатона Moscow AI Cup 2023\nGoogle Data Analytics Certificate',
                'required': False
            },
            {
                'key': 'languages',
                'text': '<b>🌍 Языки</b>\n\nУкажите уровень владения',
                'example': 'Русский (родной), Английский (C1), Немецкий (B1)',
                'required': True
            },
            {
                'key': 'interests',
                'text': '<b>🎯 Интересы и хобби</b>\n\nОпционально, но может выделить вас',
                'example': 'Машинное обучение, Open Source проекты, Бег',
                'required': False
            }
        ]
    }
}

FEEDBACK_QUESTIONS = [
    {
        'key': 'resume_rating',
        'text': '<b>Как вы оцениваете итоговое резюме?</b>\n\nПоставьте оценку от 1 до 5',
        'type': 'rating'
    },
    {
        'key': 'will_use',
        'text': '<b>Будете ли использовать это резюме для подачи на вакансию?</b>',
        'type': 'yes_no'
    },
    {
        'key': 'editing_time',
        'text': '<b>Сколько времени вы потратили на редактирование резюме?</b>',
        'type': 'time'
    },
    {
        'key': 'did_edit',
        'text': '<b>Редактировали ли вы резюме?</b>\n(меняли формулировки, добавляли/удаляли информацию)',
        'type': 'yes_no'
    },
    {
        'key': 'overall_experience',
        'text': '<b>Как оцениваете общий опыт работы с ботом?</b>\n\nОт 1 до 5',
        'type': 'rating'
    }
]
