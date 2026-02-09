import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode
from datetime import datetime
import config
from database import Database
from latex_generator import LaTeXGenerator
from ai_analyzer import AIAnalyzer
from keyboards import Keyboards
import io
import http.server
import socketserver
import os
import threading

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния
(COLLECTING_DATA, VACANCY_INPUT, TEMPLATE_SELECT,
 EDIT_SECTIONS, FEEDBACK_COLLECT, MENU) = range(6)

# Инициализация
db = Database()
latex_gen = LaTeXGenerator()
ai = AIAnalyzer()
kb = Keyboards()

# Хранилище данных
user_sessions = {}


def get_user_session(user_id):
    """Получить или создать сессию пользователя"""
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            'registration_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'current_section': None,
            'current_question': 0,
            'experiences': [],
            'projects': [],
            'history': [],
            'message_ids': []
        }
    return user_sessions[user_id]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало работы"""
    user = update.effective_user
    session = get_user_session(user.id)
    session['username'] = user.username

    welcome = f"""<b>👋 Привет, {user.first_name}!</b>

Я помогу тебе создать профессиональное резюме, адаптированное под конкретную вакансию.

<b>🎯 Как это работает:</b>
1️⃣ Ответишь на вопросы о себе (10-15 мин)
2️⃣ Пришлешь текст вакансии
3️⃣ Получишь готовое резюме в LaTeX формате

<b>✨ Особенности:</b>
- AI-анализ вакансии с Google Gemini
- Автоматическая подсветка важных навыков
- Возможность редактировать разделы
- Красивое LaTeX-оформление

Готов начать? 🚀"""

    await update.message.reply_text(
        welcome,
        reply_markup=kb.main_menu(),
        parse_mode=ParseMode.HTML
    )
    return MENU


async def view_resume(update: Update, context: ContextTypes.DEFAULT_TYPE, resume_idx):
    """Просмотр конкретного резюме"""
    query = update.callback_query
    user_id = update.effective_user.id
    session = get_user_session(user_id)

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except:
        pass

    await query.message.reply_text(
        "⏳ <b>Генерирую резюме...</b>",
        parse_mode=ParseMode.HTML
    )

    # Генерируем PDF заново
    pdf_data, error = latex_gen.generate_pdf(session, session.get('vacancy_keywords'))

    if pdf_data:
        caption = f"""<b>📄 Твое резюме</b>

Дата создания: {session.get('resumes', [])[resume_idx]['date']}
Шаблон: {session.get('resumes', [])[resume_idx]['template']}"""

        await query.message.reply_document(
            document=pdf_data,
            filename=f"Resume_{session.get('full_name', 'User').replace(' ', '_')}.pdf",
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=kb.main_menu()
        )
    else:
        # .tex файл
        latex_code = latex_gen.generate_resume(session, session.get('vacancy_keywords'))
        latex_file = io.BytesIO(latex_code.encode('utf-8'))

        await query.message.reply_document(
            document=latex_file,
            filename=f"Resume_{session.get('full_name', 'User').replace(' ', '_')}.tex",
            caption=f"<b>📄 Твое резюме</b>\n\n<i>Причина .tex: {error}</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb.main_menu()
        )

    return MENU


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий кнопок"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    session = get_user_session(user_id)

    data = query.data

    # Главное меню
    if data == 'new_resume':
        return await start_collection(update, context)
    elif data == 'my_resumes':
        user_resumes = session.get('resumes', [])

        if user_resumes:
            msg = "<b>📄 Мои резюме</b>\n\nВыбери резюме для просмотра:"
            await query.edit_message_text(
                msg,
                reply_markup=kb.resume_list(user_resumes),
                parse_mode=ParseMode.HTML
            )
        else:
            await query.edit_message_text(
                """<b>📄 Мои резюме</b>

    Здесь будут отображаться твои созданные резюме.

    Пока пусто - создай первое резюме! 😊""",
                reply_markup=kb.main_menu(),
                parse_mode=ParseMode.HTML
            )
        return MENU

    elif data.startswith('view_resume_'):
        resume_idx = int(data.split('_')[2])
        return await view_resume(update, context, resume_idx)

    elif data == 'back_to_menu':
        await query.edit_message_text(
            "<b>Главное меню</b>",
            reply_markup=kb.main_menu(),
            parse_mode=ParseMode.HTML
        )
        return MENU
    elif data == 'help':
        return await help_command(update, context)
    elif data == 'feedback':
        return await start_feedback(update, context)
    elif data == 'skip_comment':
        session['feedback']['comment'] = ''
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except:
            pass
        return await finish_feedback(update, context)

    # Навигация
    elif data == 'back':
        return await go_back(update, context)
    elif data == 'skip':
        return await skip_question(update, context)
    elif data == 'continue':
        return await next_section(update, context)
    elif data == 'add_more':
        return await add_more_items(update, context)

    # Ответы
    elif data.startswith('answer_'):
        return await process_answer(update, context, data.split('_')[1])
    elif data.startswith('edit_'):
        return await edit_section(update, context, data.split('_')[1])
    elif data.startswith('delete_'):
        return await delete_section(update, context, data.split('_')[1])
    elif data.startswith('add_'):
        return await add_section(update, context, data.split('_')[1])
    elif data == 'finalize':
        return await finalize_resume(update, context)

    # Feedback
    elif data.startswith('rating_'):
        return await save_rating(update, context, data.split('_')[1])
    elif data.startswith('time_'):
        return await save_time(update, context, data.split('_')[1])

    return MENU


async def start_collection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало сбора данных"""
    query = update.callback_query
    user_id = update.effective_user.id
    session = get_user_session(user_id)

    # Деактивируем кнопки главного меню
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except:
        pass

    # Сбрасываем состояние
    session['current_section'] = 'personal'
    session['current_question'] = 0
    session['history'] = []

    msg = "<b>📝 Отлично! Начнем заполнение данных</b>\n\n"
    msg += "Ты можешь в любой момент вернуться назад с помощью кнопки Назад.\n\n"
    msg += "Поехали! 🚀"

    await query.message.reply_text(msg, parse_mode=ParseMode.HTML)

    # Задаем первый вопрос
    await ask_current_question(update, context)
    return COLLECTING_DATA


async def ask_current_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Задать текущий вопрос"""
    user_id = update.effective_user.id if update.callback_query else update.message.from_user.id
    session = get_user_session(user_id)

    section_key = session['current_section']
    question_idx = session['current_question']

    section = config.QUESTIONS_STRUCTURE.get(section_key)
    if not section:
        await next_section(update, context)
        return

    questions = section['questions']

    if question_idx >= len(questions):
        # Проверяем, нужно ли добавить еще элементов (для опыта/проектов)
        if section.get('multiple'):
            keyboard = kb.add_more_back()
            items_count = len(session.get(section_key + 's', []))

            msg = f"<b>✅ {section['title']}</b>\n\n"
            if items_count > 0:
                msg += f"Добавлено записей: <b>{items_count}</b>\n\n"
            msg += "Хочешь добавить еще одну запись?"

            if update.callback_query:
                await update.callback_query.message.reply_text(
                    msg,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text(
                    msg,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
        else:
            await next_section(update, context)
        return

    question = questions[question_idx]

    msg = f"<b>{section['title']}</b>\n\n"
    msg += question['text']

    if question.get('example'):
        msg += f"\n\n<i>💡 Пример: {question['example']}</i>"

    # Клавиатура - ВСЕГДА показываем кнопки Пропустить/Назад
    keyboard = kb.skip_back()

    if update.callback_query:
        await update.callback_query.message.reply_text(
            msg,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            msg,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )


async def process_text_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстового ответа"""
    user_id = update.message.from_user.id
    session = get_user_session(user_id)
    text = update.message.text

    # Проверяем состояние
    if session.get('waiting_for') == 'vacancy':
        return await process_vacancy(update, context)

    section_key = session['current_section']
    question_idx = session['current_question']

    section = config.QUESTIONS_STRUCTURE.get(section_key)
    if not section:
        return COLLECTING_DATA

    questions = section['questions']
    if question_idx >= len(questions):
        return COLLECTING_DATA

    question = questions[question_idx]

    # Сохраняем ответ
    if section.get('multiple'):
        current_item = session.get('current_item', {})
        current_item[question['key']] = text
        session['current_item'] = current_item
    else:
        session[question['key']] = text

    # История для возврата назад
    if not session.get('editing_mode'):
        session['history'].append({
            'section': section_key,
            'question': question_idx,
            'value': text
        })

    # Если режим редактирования - сразу возвращаемся к редактору после завершения раздела
    if session.get('editing_mode'):
        session['current_question'] += 1

        # Проверяем завершили ли редактирование раздела
        if section.get('multiple'):
            # Для multiple разделов - сохраняем и возвращаемся
            items_key = section_key + 's'
            if items_key not in session:
                session[items_key] = []

            current_item = session.get('current_item', {})
            if current_item:
                # Обновляем существующий или добавляем новый
                if session.get('editing_item_index') is not None:
                    session[items_key][session['editing_item_index']] = current_item
                else:
                    session[items_key].append(current_item)
                session['current_item'] = {}

            session['editing_mode'] = False
            session['editing_item_index'] = None
            await update.message.reply_text(
                "✅ <b>Раздел обновлен!</b>",
                parse_mode=ParseMode.HTML
            )
            return await show_sections_editor(update, context)
        elif session['current_question'] >= len(questions):
            session['editing_mode'] = False
            await update.message.reply_text(
                "✅ <b>Раздел обновлен!</b>",
                parse_mode=ParseMode.HTML
            )
            return await show_sections_editor(update, context)
        else:
            await ask_current_question(update, context)
            return COLLECTING_DATA

    # Переход к следующему вопросу
    session['current_question'] += 1
    await ask_current_question(update, context)

    return COLLECTING_DATA


async def skip_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропустить вопрос"""
    query = update.callback_query
    user_id = update.effective_user.id
    session = get_user_session(user_id)

    # Деактивируем кнопки
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except:
        pass

    section_key = session['current_section']
    section = config.QUESTIONS_STRUCTURE.get(section_key)

    # Если пропускаем первый вопрос в education - пропускаем всю секцию
    if section_key == 'education' and session['current_question'] == 0:
        await query.message.reply_text(
            "<i>⏭ Пропускаем образование...</i>",
            parse_mode=ParseMode.HTML
        )
        return await next_section(update, context)

    # Для секций с multiple - переходим к следующей секции при пропуске первого вопроса
    if section and section.get('multiple') and session['current_question'] == 0:
        await query.message.reply_text(
            f"<i>⏭ Пропускаем {section['title']}...</i>",
            parse_mode=ParseMode.HTML
        )
        return await next_section(update, context)

    session['current_question'] += 1
    await ask_current_question(update, context)

    return COLLECTING_DATA


async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться назад"""
    query = update.callback_query
    user_id = update.effective_user.id
    session = get_user_session(user_id)

    # Деактивируем кнопки
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except:
        pass

    if not session.get('history'):
        await query.message.reply_text("Это первый вопрос!")
        await ask_current_question(update, context)
        return COLLECTING_DATA

    # Восстанавливаем предыдущее состояние
    last_state = session['history'].pop()
    session['current_section'] = last_state['section']
    session['current_question'] = last_state['question']

    await query.message.reply_text("<i>◀️ Возвращаемся назад...</i>", parse_mode=ParseMode.HTML)
    await ask_current_question(update, context)

    return COLLECTING_DATA


async def add_more_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить еще элемент (опыт/проект)"""
    query = update.callback_query
    user_id = update.effective_user.id
    session = get_user_session(user_id)

    # Деактивируем кнопки
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except:
        pass

    section_key = session['current_section']

    # ВАЖНО: Сохраняем текущий элемент ПЕРЕД добавлением нового
    current_item = session.get('current_item', {})
    if current_item:
        items_key = section_key + 's'
        if items_key not in session:
            session[items_key] = []

        # Проверяем что элемент не пустой
        if any(current_item.values()):
            session[items_key].append(current_item)
            print(f"Saved item to {items_key}: {current_item}")  # Debug

        session['current_item'] = {}

    # Начинаем заново с первого вопроса этой секции
    session['current_question'] = 0

    await query.message.reply_text(
        "<b>➕ Добавляем еще одну запись</b>",
        parse_mode=ParseMode.HTML
    )
    await ask_current_question(update, context)

    return COLLECTING_DATA


async def next_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переход к следующей секции"""
    query = update.callback_query if update.callback_query else None
    user_id = update.effective_user.id if query else update.message.from_user.id
    session = get_user_session(user_id)

    # Деактивируем кнопки
    if query:
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except:
            pass

    # ВАЖНО: Сохраняем текущий элемент если есть (для опыта/проектов)
    if session.get('current_item'):
        section_key = session['current_section']
        items_key = section_key + 's'

        current_item = session['current_item']
        if any(current_item.values()):  # Проверяем что не пустой
            if items_key not in session:
                session[items_key] = []
            session[items_key].append(current_item)
            print(f"Saved item in next_section to {items_key}: {current_item}")  # Debug

        session['current_item'] = {}

    # Определяем следующую секцию
    sections_order = ['personal', 'education', 'experience', 'projects', 'skills', 'additional']
    current_idx = sections_order.index(session['current_section']) if session[
                                                                          'current_section'] in sections_order else -1

    if current_idx < len(sections_order) - 1:
        session['current_section'] = sections_order[current_idx + 1]
        session['current_question'] = 0
        await ask_current_question(update, context)
        return COLLECTING_DATA
    else:
        # Все секции пройдены - запрашиваем вакансию
        return await request_vacancy(update, context)


async def request_vacancy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос текста вакансии"""
    query = update.callback_query if update.callback_query else None
    user_id = update.effective_user.id if query else update.message.from_user.id
    session = get_user_session(user_id)

    session['waiting_for'] = 'vacancy'

    msg = """<b>✅ Отлично! Базовая информация собрана</b>

📋 Теперь пришли мне <b>текст вакансии</b>, на которую хочешь откликнуться.

Просто скопируй описание вакансии с сайта (HH, LinkedIn и т.д.) и отправь сюда.

🤖 Я проанализирую требования с помощью AI и выделю ключевые слова для твоего резюме!"""

    if query:
        await query.message.reply_text(msg, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    return VACANCY_INPUT


async def process_vacancy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текста вакансии"""
    user_id = update.message.from_user.id
    session = get_user_session(user_id)
    vacancy_text = update.message.text

    session['vacancy_text'] = vacancy_text
    session['waiting_for'] = None

    # Анализ вакансии
    analyzing_msg = await update.message.reply_text(
        "🔍 <b>Анализирую вакансию...</b>",
        parse_mode=ParseMode.HTML
    )

    try:
        keywords = ai.extract_keywords_from_vacancy(vacancy_text)
        session['vacancy_keywords'] = keywords

        await analyzing_msg.delete()

        # Результат анализа
        result_msg = ai.format_keywords_message(keywords)
        await update.message.reply_text(result_msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        await analyzing_msg.delete()
        logger.error(f"AI analysis error: {e}")
        await update.message.reply_text(
            "⚠️ Не удалось подключиться к AI (проблема с VPN или интернетом).\n\n"
            "Продолжаем без AI-анализа.",
            parse_mode=ParseMode.HTML
        )
        session['vacancy_keywords'] = {'technical': [], 'soft': [], 'keywords': []}

    # Сразу переходим к редактированию
    session['template'] = 'Современный (Jake\'s Resume)'
    session['template_id'] = 'modern'

    msg = """<b>📝 Структура резюме</b>

Сейчас ты можешь изменить структуру резюме:
- Отредактировать разделы
- Удалить ненужные
- Добавить пропущенные

Когда все будет готово, нажми "Готово, создать резюме" """

    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    # Переход к редактированию разделов
    return await show_sections_editor(update, context)


async def show_sections_editor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать редактор разделов"""
    query = update.callback_query if update.callback_query else None
    user_id = update.effective_user.id if query else update.message.from_user.id
    session = get_user_session(user_id)

    msg = "<b>Редактирование разделов резюме</b>\n\n"

    # Собираем данные для клавиатуры
    user_sections = {
        'education': bool(session.get('university')),
        'experience': bool(session.get('experiences')),
        'projects': bool(session.get('projects')),
        'skills': bool(session.get('technical_skills')),
        'achievements': bool(session.get('achievements')),
        'languages': bool(session.get('languages')),
        'interests': bool(session.get('interests'))
    }

    # Показываем какие разделы заполнены
    filled = [name for name, filled in [
        ('Образование', user_sections['education']),
        ('Опыт работы', user_sections['experience']),
        ('Проекты', user_sections['projects']),
        ('Навыки', user_sections['skills']),
        ('Достижения', user_sections['achievements']),
        ('Языки', user_sections['languages']),
        ('Интересы', user_sections['interests'])
    ] if filled]

    if filled:
        msg += "<b>Заполненные разделы:</b>\n"
        msg += "• " + "\n• ".join(filled) + "\n\n"

    msg += "Используй кнопки ниже для редактирования."

    if query:
        await query.message.reply_text(
            msg,
            reply_markup=kb.sections_edit(user_sections),
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            msg,
            reply_markup=kb.sections_edit(user_sections),
            parse_mode=ParseMode.HTML
        )

    return EDIT_SECTIONS


async def edit_section(update: Update, context: ContextTypes.DEFAULT_TYPE, section_id):
    """Редактирование раздела"""
    query = update.callback_query
    user_id = update.effective_user.id
    session = get_user_session(user_id)

    # Деактивируем кнопки
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except:
        pass

    # Показываем текущие данные
    current_data = []
    if section_id == 'education':
        if session.get('university'):
            current_data.append(f"Университет: {session.get('university')}")
            current_data.append(f"Специальность: {session.get('degree')}")
            current_data.append(f"Период: {session.get('study_period')}")
    elif section_id == 'experience':
        for i, exp in enumerate(session.get('experiences', []), 1):
            current_data.append(f"{i}. {exp.get('position')} в {exp.get('company')}")
    elif section_id == 'projects':
        for i, proj in enumerate(session.get('projects', []), 1):
            current_data.append(f"{i}. {proj.get('project_name')}")
    elif section_id == 'skills':
        current_data.append(f"Технические: {session.get('technical_skills', '')[:50]}...")
    elif section_id == 'achievements':
        ach = session.get('achievements', '')
        if ach:
            current_data.append(f"{ach[:100]}...")
    elif section_id == 'languages':
        current_data.append(session.get('languages', ''))
    elif section_id == 'interests':
        current_data.append(session.get('interests', ''))

    msg = "<b>✏️ Редактирование раздела</b>\n\n"
    if current_data:
        msg += "<b>Текущие данные:</b>\n"
        msg += "\n".join(current_data)
        msg += "\n\n"
    msg += "Отправь новые данные или нажми Пропустить для сохранения текущих"

    # Сохраняем что мы редактируем конкретный раздел
    session['editing_mode'] = True
    session['editing_section_id'] = section_id

    # Устанавливаем текущую секцию для редактирования
    section_map = {
        'education': ('education', 0),
        'experience': ('experience', 0),
        'projects': ('projects', 0),
        'skills': ('skills', 0),
        'achievements': ('additional', 0),
        'languages': ('additional', 1),
        'interests': ('additional', 2)
    }

    if section_id in section_map:
        section_key, question_offset = section_map[section_id]
        session['current_section'] = section_key
        session['current_question'] = question_offset

        # Для additional находим правильный вопрос
        if section_key == 'additional':
            section_data = config.QUESTIONS_STRUCTURE.get('additional')
            if section_data:
                for idx, q in enumerate(section_data['questions']):
                    if section_id in q['key']:
                        session['current_question'] = idx
                        break

    await query.message.reply_text(msg, parse_mode=ParseMode.HTML)
    await ask_current_question(update, context)

    return COLLECTING_DATA


async def delete_section(update: Update, context: ContextTypes.DEFAULT_TYPE, section_id):
    """Удаление раздела"""
    query = update.callback_query
    user_id = update.effective_user.id
    session = get_user_session(user_id)

    # Деактивируем кнопки
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except:
        pass

    # Очищаем данные раздела
    section_keys_map = {
        'education': ['university', 'degree', 'study_period', 'gpa'],
        'experience': ['experiences'],
        'projects': ['projects'],
        'skills': ['technical_skills', 'soft_skills'],
        'achievements': ['achievements'],
        'languages': ['languages'],
        'interests': ['interests']
    }

    keys_to_clear = section_keys_map.get(section_id, [])
    for key in keys_to_clear:
        if key in session:
            session[key] = [] if key in ['experiences', 'projects'] else ''

    await query.message.reply_text(
        f"<b>🗑 Раздел удален</b>",
        parse_mode=ParseMode.HTML
    )

    return await show_sections_editor(update, context)


async def add_section(update: Update, context: ContextTypes.DEFAULT_TYPE, section_id):
    """Добавление раздела"""
    return await edit_section(update, context, section_id)


async def finalize_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Финализация и создание резюме"""
    query = update.callback_query
    user_id = update.effective_user.id
    username = update.effective_user.username
    session = get_user_session(user_id)

    # Деактивируем кнопки
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except:
        pass

    creating_msg = await query.message.reply_text(
        "⏳ <b>Создаю твое резюме...</b>",
        parse_mode=ParseMode.HTML
    )

    # Сохраняем в Google Sheets
    session['status'] = 'completed'
    session['resume_date'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    db.save_user_data(user_id, username, session)

    # Генерируем PDF
    pdf_data, error = latex_gen.generate_pdf(session, session.get('vacancy_keywords'))

    await creating_msg.delete()

    if pdf_data:
        # Отправляем PDF
        caption = """<b>🎉 Твое резюме готово!</b>

✅ Ключевые слова из вакансии выделены синим
✅ Формат оптимизирован для ATS-систем
✅ Профессиональное оформление

Удачи с откликами! 🚀"""

        await query.message.reply_document(
            document=pdf_data,
            filename=f"Resume_{session.get('full_name', 'User').replace(' ', '_')}.pdf",
            caption=caption,
            parse_mode=ParseMode.HTML
        )
    else:
        # Если PDF не создался, отправляем .tex файл
        latex_code = latex_gen.generate_resume(session, session.get('vacancy_keywords'))
        latex_file = io.BytesIO(latex_code.encode('utf-8'))

        caption = f"""<b>📝 Твое резюме готово!</b>

✅ Ключевые слова из вакансии выделены синим
✅ Формат оптимизирован для ATS-систем

<b>Как получить PDF:</b>
1. Открой файл в Overleaf (overleaf.com)
2. Нажми Recompile
3. Скачай PDF

<i>Причина .tex формата: {error or 'PDF компилятор недоступен'}</i>"""

        await query.message.reply_document(
            document=latex_file,
            filename=f"Resume_{session.get('full_name', 'User').replace(' ', '_')}.tex",
            caption=caption,
            parse_mode=ParseMode.HTML
        )

    # Сохраняем резюме в сессию для "Мои резюме"
    if 'resumes' not in session:
        session['resumes'] = []
    session['resumes'].append({
        'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'name': session.get('full_name', 'Резюме'),
        'template': session.get('template', 'Modern')
    })

    # Запускаем сбор feedback
    return await start_feedback(update, context)


async def start_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало сбора обратной связи"""
    query = update.callback_query if update.callback_query else None
    user_id = update.effective_user.id if query else update.message.from_user.id
    session = get_user_session(user_id)

    session['feedback'] = {}
    session['feedback_question'] = 0

    msg = """<b>💭 Обратная связь</b>

Пожалуйста, ответь на несколько вопросов о своем опыте.
Это очень важно для нашего исследования! 🙏"""

    if query:
        await query.message.reply_text(msg, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    await ask_feedback_question(update, context)

    return FEEDBACK_COLLECT


async def ask_feedback_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Задать вопрос обратной связи"""
    user_id = update.effective_user.id if update.callback_query else update.message.from_user.id
    session = get_user_session(user_id)

    idx = session.get('feedback_question', 0)

    if idx >= len(config.FEEDBACK_QUESTIONS):
        # Последний вопрос - запрашиваем комментарий
        if not session['feedback'].get('comment_requested'):
            session['feedback']['comment_requested'] = True
            msg = "<b>Хочешь оставить комментарий?</b>\n\n"
            msg += "Напиши свои мысли о боте или нажми Пропустить"

            keyboard = [[InlineKeyboardButton("Пропустить", callback_data="skip_comment")]]

            if update.callback_query:
                await update.callback_query.message.reply_text(
                    msg,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text(
                    msg,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.HTML
                )
            return FEEDBACK_COLLECT
        else:
            return await finish_feedback(update, context)

    question = config.FEEDBACK_QUESTIONS[idx]

    keyboard = None
    if question['type'] == 'rating':
        keyboard = kb.rating(5)
    elif question['type'] == 'yes_no':
        keyboard = kb.yes_no()
    elif question['type'] == 'time':
        keyboard = kb.time_options()

    if update.callback_query:
        await update.callback_query.message.reply_text(
            question['text'],
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            question['text'],
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )


async def save_rating(update: Update, context: ContextTypes.DEFAULT_TYPE, rating):
    """Сохранить оценку"""
    query = update.callback_query
    user_id = update.effective_user.id
    session = get_user_session(user_id)

    # Деактивируем кнопки
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except:
        pass

    idx = session.get('feedback_question', 0)
    question = config.FEEDBACK_QUESTIONS[idx]

    session['feedback'][question['key']] = rating
    session['feedback_question'] += 1

    await query.message.reply_text(f"✅ Оценка: {rating}", parse_mode=ParseMode.HTML)
    await ask_feedback_question(update, context)

    return FEEDBACK_COLLECT


async def save_time(update: Update, context: ContextTypes.DEFAULT_TYPE, time_code):
    """Сохранить время"""
    query = update.callback_query
    user_id = update.effective_user.id
    session = get_user_session(user_id)

    # Деактивируем кнопки
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except:
        pass

    time_map = {
        '15': 'Менее 15 минут',
        '30': '15-30 минут',
        '60': '30-60 минут',
        '60plus': 'Больше часа'
    }

    idx = session.get('feedback_question', 0)
    question = config.FEEDBACK_QUESTIONS[idx]

    session['feedback'][question['key']] = time_map.get(time_code, time_code)
    session['feedback_question'] += 1

    await query.message.reply_text(f"✅ Время: {time_map.get(time_code)}", parse_mode=ParseMode.HTML)
    await ask_feedback_question(update, context)

    return FEEDBACK_COLLECT


async def process_answer(update: Update, context: ContextTypes.DEFAULT_TYPE, answer):
    """Обработка ответа да/нет"""
    query = update.callback_query
    user_id = update.effective_user.id
    session = get_user_session(user_id)

    # Деактивируем кнопки
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except:
        pass

    idx = session.get('feedback_question', 0)
    question = config.FEEDBACK_QUESTIONS[idx]

    answer_text = 'Да' if answer == 'yes' else 'Нет'
    session['feedback'][question['key']] = answer_text
    session['feedback_question'] += 1
    await query.message.reply_text(f"✅ Ответ: {answer_text}", parse_mode=ParseMode.HTML)
    await ask_feedback_question(update, context)

    return FEEDBACK_COLLECT


async def finish_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение сбора обратной связи"""
    user_id = update.effective_user.id if update.callback_query else update.message.from_user.id
    username = update.effective_user.username if update.callback_query else update.message.from_user.username
    session = get_user_session(user_id)

    # Сохраняем feedback
    db.save_feedback(user_id, username, session.get('feedback', {}))

    try:
        db.update_analytics()
    except Exception as e:
        logger.error(f"Analytics error: {e}")

    msg = """<b>🎉 Спасибо за участие в исследовании!</b>

Твои ответы очень помогут нам улучшить продукт.

<b>📬 Связь с нами:</b>
Telegram: @karbarkarrr

Если у тебя есть вопросы или предложения, пиши!

Удачи в поиске работы! 🚀"""

    if update.callback_query:
        await update.callback_query.message.reply_text(
            msg,
            reply_markup=kb.main_menu(),
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            msg,
            reply_markup=kb.main_menu(),
            parse_mode=ParseMode.HTML
        )

    return MENU


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь"""
    help_text = """<b>🤖 Помощь по боту</b>

<b>📝 Как пользоваться:</b>
- Нажми "Создать новое резюме"
- Ответь на вопросы о себе
- Пришли текст вакансии
- Отредактируй разделы при необходимости
- Получи готовый pdf файл

<b>✨ Особенности:</b>
- В любой момент можно вернуться назад
- Любой раздел можно пропустить
- После создания можно редактировать разделы
- AI анализирует вакансию и выделяет ключевые слова

<b>📬 Поддержка:</b>
@karbarkarrr

<b>🎯 О боте:</b>
Прототип для UX-исследования по упрощению создания резюме для студентов и молодых специалистов."""

    if update.callback_query:
        await update.callback_query.edit_message_text(
            help_text,
            reply_markup=kb.main_menu(),
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            help_text,
            reply_markup=kb.main_menu(),
            parse_mode=ParseMode.HTML
        )

    return MENU


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена"""

    await update.message.reply_text(
        "❌ Действие отменено. Используй /start для начала",
        reply_markup=kb.main_menu(),
        parse_mode=ParseMode.HTML
    )
    return MENU


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /new"""

    user_id = update.effective_user.id
    session = get_user_session(user_id)
    session['username'] = update.effective_user.username
    # Сбрасываем состояние
    session['current_section'] = 'personal'
    session['current_question'] = 0
    session['history'] = []

    msg = "<b>📝 Начинаем создание нового резюме!</b>\n\nПоехали! 🚀"
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    await ask_current_question(update, context)
    return COLLECTING_DATA


# Обработчик ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ошибок"""
    logger.error(f"Update {update} caused error {context.error}")

    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "😔 Произошла ошибка. Попробуй еще раз или напиши /start",
                parse_mode=ParseMode.HTML
            )
        except:
            pass


async def process_feedback_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка комментария в feedback"""
    user_id = update.message.from_user.id
    session = get_user_session(user_id)

    if session['feedback'].get('comment_requested'):
        session['feedback']['comment'] = update.message.text
        await update.message.reply_text("✅ Спасибо за комментарий!", parse_mode=ParseMode.HTML)
        return await finish_feedback(update, context)

    return FEEDBACK_COLLECT


async def feedback_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /feedback"""
    return await start_feedback(update, context)


def main():
    """Запуск бота"""
    application = Application.builder().token(config.TELEGRAM_TOKEN).build()

    # Добавляем обработчик ошибок
    application.add_error_handler(error_handler)

    # Conversation handler с правильными настройками
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CommandHandler('new', new_command)
        ],
        states={
            MENU: [
                CallbackQueryHandler(button_handler),
                CommandHandler('new', new_command),
                CommandHandler('help', help_command),
                CommandHandler('feedback', start_feedback)
            ],
            COLLECTING_DATA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_text_answer),
                CallbackQueryHandler(button_handler)
            ],
            VACANCY_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_vacancy),
                CallbackQueryHandler(button_handler)
            ],
            TEMPLATE_SELECT: [
                CallbackQueryHandler(button_handler)
            ],
            EDIT_SECTIONS: [
                CallbackQueryHandler(button_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_text_answer)
            ],
            FEEDBACK_COLLECT: [
                CallbackQueryHandler(button_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_feedback_comment)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False,
        per_chat=True,
        per_user=True
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('feedback', feedback_cmd))

    logger.info("🤖 Bot started!")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True  # Игнорируем старые обновления
    )


def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        httpd.serve_forever()


if __name__ == '__main__':
    threading.Thread(target=run_dummy_server, daemon=True).start()
    main()
