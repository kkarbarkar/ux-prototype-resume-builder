import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode
from telegram.error import BadRequest
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
import time
import re
import html
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

(COLLECTING_DATA, VACANCY_INPUT, TEMPLATE_SELECT,
 EDIT_SECTIONS, FEEDBACK_COLLECT, MENU) = range(6)

db = Database()
latex_gen = LaTeXGenerator()
ai = AIAnalyzer()
kb = Keyboards()
AI_REWRITE_FIELDS = {'responsibilities', 'project_description', 'achievements', 'interests'}
URL_PATTERN = re.compile(r'https?://[^\s<>"\]\)]+', re.IGNORECASE)

user_sessions = {}


def get_user_session(user_id):
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            'registration_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'current_section': None,
            'current_question': 0,
            'educations': [],
            'experiences': [],
            'projects': [],
            'history': [],
            'message_ids': []
        }
        saved = db.get_user_data(user_id)
        if saved:
            mapping = {
                'ФИО': 'full_name',
                'Email': 'email',
                'Телефон': 'phone',
                'Город': 'location',
                'LinkedIn': 'linkedin',
                'GitHub': 'github',
                'GitLab': 'gitlab',
                'Portfolio': 'portfolio',
                'Университет': 'university',
                'Специальность': 'degree',
                'Период обучения': 'study_period',
                'Технические навыки': 'technical_skills',
                'Soft skills': 'soft_skills',
                'Достижения': 'achievements',
                'Языки': 'languages',
                'Интересы': 'interests',
                'Текст вакансии': 'vacancy_text',
                'Ссылка на вакансию': 'vacancy_url',
                'Выбранный шаблон': 'template',
                'Дата создания резюме': 'resume_date',
                'Статус': 'status'
            }
            for src, dst in mapping.items():
                if src in saved and saved[src]:
                    user_sessions[user_id][dst] = saved[src]
            for key in ['educations', 'experiences', 'projects', 'vacancy_keywords']:
                if key in saved:
                    user_sessions[user_id][key] = saved[key]
            if not user_sessions[user_id].get('educations'):
                if saved.get('Университет') or saved.get('Специальность') or saved.get('Период обучения'):
                    user_sessions[user_id]['educations'] = [{
                        'university': saved.get('Университет', ''),
                        'degree': saved.get('Специальность', ''),
                        'study_period': saved.get('Период обучения', '')
                    }]
            if saved.get('status') == 'completed' and saved.get('resume_date'):
                user_sessions[user_id]['resumes'] = [{
                    'date': saved.get('resume_date'),
                    'name': saved.get('full_name', 'Резюме'),
                    'template': saved.get('template', 'Modern')
                }]
    return user_sessions[user_id]

def _items_key(section_key):
    return section_key if section_key.endswith('s') else section_key + 's'


def _extract_first_url(text):
    if not text:
        return None
    match = URL_PATTERN.search(text)
    return match.group(0) if match else None


def _html_to_text(raw_html):
    if not raw_html:
        return ''

    cleaned = re.sub(r'(?is)<(script|style|noscript|svg).*?>.*?</\1>', ' ', raw_html)
    title_match = re.search(r'(?is)<title[^>]*>(.*?)</title>', raw_html)
    title = html.unescape(title_match.group(1)).strip() if title_match else ''
    body_text = re.sub(r'(?is)<[^>]+>', ' ', cleaned)
    body_text = html.unescape(body_text)
    body_text = re.sub(r'\s+', ' ', body_text).strip()

    if title and title.lower() not in body_text.lower():
        return f"{title}\n{body_text}"
    return body_text


def _fetch_vacancy_text_from_url(url, timeout=15):
    try:
        request = Request(
            url,
            headers={
                'User-Agent': (
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/123.0.0.0 Safari/537.36'
                ),
                'Accept-Language': 'ru,en;q=0.9'
            }
        )
        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' not in content_type and 'application/xhtml+xml' not in content_type:
                return '', f'Неподдерживаемый формат страницы: {content_type or "unknown"}'

            raw_bytes = response.read(2_000_000)
            charset = response.headers.get_content_charset() or 'utf-8'
            raw_html = raw_bytes.decode(charset, errors='ignore')
            extracted = _html_to_text(raw_html)
            if len(extracted) < 200:
                return '', 'На странице слишком мало текста для анализа'

            return extracted[:30000], ''
    except HTTPError as e:
        return '', f'HTTP {e.code}'
    except URLError as e:
        return '', f'Ошибка сети: {e.reason}'
    except Exception as e:
        return '', str(e)

def _reset_resume_data(session):
    keys = [
        'full_name', 'email', 'phone', 'location', 'linkedin', 'github', 'gitlab', 'portfolio',
        'university', 'degree', 'study_period', 'educations', 'experiences', 'projects',
        'technical_skills', 'soft_skills', 'achievements', 'languages', 'interests',
        'vacancy_text', 'vacancy_url', 'vacancy_keywords', 'template', 'template_id', 'status',
        'resume_date', 'current_item'
    ]
    for key in keys:
        if key in ['educations', 'experiences', 'projects']:
            session[key] = []
        elif key == 'vacancy_keywords':
            session[key] = {}
        else:
            session[key] = ''
    session['waiting_for'] = None
    session['current_item'] = {}


IGNORABLE_REPLY_MARKUP_ERRORS = (
    "message is not modified",
    "message to edit not found",
    "message can't be edited",
    "there is no reply markup in the message",
    "query is too old",
)


def _is_ignorable_reply_markup_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(pattern in text for pattern in IGNORABLE_REPLY_MARKUP_ERRORS)


def _sync_primary_education_from_list(session):
    educations = session.get('educations') or []
    if not educations:
        session['university'] = ''
        session['degree'] = ''
        session['study_period'] = ''
        return
    first = educations[0] or {}
    session['university'] = first.get('university', '')
    session['degree'] = first.get('degree', '')
    session['study_period'] = first.get('study_period', '')


async def safe_answer_callback_query(query):
    try:
        await query.answer()
    except BadRequest as exc:
        if "query is too old" not in str(exc).lower() and "query_id_invalid" not in str(exc).lower():
            logger.warning("Ошибка answerCallbackQuery: %s", exc)


def is_fast_duplicate_click(session, query):
    if not query or not query.message:
        return False
    click_key = f"{query.message.message_id}:{query.data}"
    now = time.monotonic()
    last = session.get('last_click')
    session['last_click'] = {'key': click_key, 'ts': now}
    return bool(last and last.get('key') == click_key and now - float(last.get('ts', 0)) < 1.2)


async def clear_reply_markup_from_query(query):
    if not query:
        return
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except BadRequest as exc:
        if not _is_ignorable_reply_markup_error(exc):
            logger.warning("Не удалось снять клавиатуру: %s", exc)
    except Exception as exc:
        logger.warning("Неожиданная ошибка при снятии клавиатуры: %s", exc)


async def clear_reply_markup_by_message(context, chat_id, message_id):
    if not chat_id or not message_id:
        return
    try:
        await context.bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=None
        )
    except BadRequest as exc:
        if not _is_ignorable_reply_markup_error(exc):
            logger.warning("Не удалось снять клавиатуру у сообщения %s: %s", message_id, exc)
    except Exception as exc:
        logger.warning("Неожиданная ошибка при снятии клавиатуры у сообщения %s: %s", message_id, exc)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    session = get_user_session(user.id)
    session['username'] = user.username
    session['editing_mode'] = False
    session['editing_section_id'] = None

    welcome = f"""<b>👋 Привет, {user.first_name}!</b>

Я помогу тебе создать профессиональное резюме, адаптированное под конкретную вакансию.

<b>🎯 Как это работает:</b>
1. Ответишь на вопросы о себе (10-15 мин)
2. Пришлешь текст вакансии
3. Получишь готовое резюме в PDF

<b>✨ Особенности:</b>
- Анализ вакансии и выделение ключевых требований
- Автоматическая подсветка важных навыков
- Возможность редактировать разделы

Готов начать? """

    await update.message.reply_text(
        welcome,
        reply_markup=kb.main_menu(),
        parse_mode=ParseMode.HTML
    )
    return MENU


async def view_resume(update: Update, context: ContextTypes.DEFAULT_TYPE, resume_idx):
    query = update.callback_query
    user_id = update.effective_user.id
    session = get_user_session(user_id)

    await clear_reply_markup_from_query(query)

    await query.message.reply_text(
        "⏳ <b>Генерирую резюме...</b>\nЭто займет до 2 минут.",
        parse_mode=ParseMode.HTML
    )
    pdf_data, error = latex_gen.generate_pdf(session, session.get('vacancy_keywords'))

    if pdf_data:
        caption = f"""<b>📄 Твое резюме</b>

Дата создания: {session.get('resumes', [])[resume_idx]['date']}"""

        await query.message.reply_document(
            document=pdf_data,
            filename=f"Resume_{session.get('full_name', 'User').replace(' ', '_')}.pdf",
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=kb.main_menu()
        )
    else:
        latex_code = latex_gen.generate_resume(session, session.get('vacancy_keywords'))
        latex_file = io.BytesIO(latex_code.encode('utf-8'))

        await query.message.reply_document(
            document=latex_file,
            filename=f"Resume_{session.get('full_name', 'User').replace(' ', '_')}.tex",
            caption="<b>📄 Твое резюме</b>\n\n<i>Отправляю в формате .tex</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb.main_menu()
        )

    return MENU


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback_query(query)

    user_id = update.effective_user.id
    session = get_user_session(user_id)
    if is_fast_duplicate_click(session, query):
        return MENU

    data = query.data
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
                "<b>📄 Мои резюме</b>\n\n"
                "Здесь будут отображаться твои созданные резюме.\n\n"
                "Пока пусто - создай первое резюме!",
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
        await clear_reply_markup_from_query(query)
        return await finish_feedback(update, context)

    elif data == 'back':
        return await go_back(update, context)
    elif data == 'skip':
        return await skip_question(update, context)
    elif data == 'continue':
        return await next_section(update, context)
    elif data == 'add_more':
        return await add_more_items(update, context)

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

    elif data.startswith('rating_'):
        return await save_rating(update, context, data.split('_')[1])
    elif data.startswith('time_'):
        return await save_time(update, context, data.split('_')[1])

    return MENU


async def start_collection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    session = get_user_session(user_id)
    await clear_reply_markup_from_query(query)
    _reset_resume_data(session)
    session['current_section'] = 'personal'
    session['current_question'] = 0
    session['history'] = []

    msg = "<b>📝 Отлично! Начнем заполнение данных</b>\n\n"
    msg += "Ты можешь в любой момент вернуться назад с помощью кнопки Назад.\n\n"
    msg += "Поехали! "

    await query.message.reply_text(msg, parse_mode=ParseMode.HTML)
    await ask_current_question(update, context)
    return COLLECTING_DATA


async def ask_current_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.callback_query else update.message.from_user.id
    session = get_user_session(user_id)

    last_question_id = session.get('last_question_message_id')
    if last_question_id:
        await clear_reply_markup_by_message(context, update.effective_chat.id, last_question_id)

    section_key = session['current_section']
    question_idx = session['current_question']

    section = config.QUESTIONS_STRUCTURE.get(section_key)
    if not section:
        await next_section(update, context)
        return

    questions = section['questions']

    if question_idx >= len(questions):
        if session.get('editing_mode'):
            session['editing_mode'] = False
            session['editing_section_id'] = None
            session['editing_item_index'] = None
            if update.callback_query:
                await update.callback_query.message.reply_text(
                    "<b>Раздел обновлен!</b>",
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text(
                    "<b>Раздел обновлен!</b>",
                    parse_mode=ParseMode.HTML
                )
            await show_sections_editor(update, context)
            return

        if section.get('multiple'):
            keyboard = kb.add_more_back()
            items_key = _items_key(section_key)
            items_count = len(session.get(items_key, []))
            current_item = session.get('current_item', {})
            if current_item and any(current_item.values()):
                items_count += 1

            msg = f"<b>{section['title']}</b>\n\n"
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
        msg += f"\n\n<i>Пример: {question['example']}</i>"

    keyboard = kb.skip_back()

    if update.callback_query:
        message = await update.callback_query.message.reply_text(
            msg,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    else:
        message = await update.message.reply_text(
            msg,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    session['last_question_message_id'] = message.message_id


async def process_text_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    session = get_user_session(user_id)
    text = update.message.text
    stripped = (text or '').strip().lower()

    if stripped in ('\\start', '\\new'):
        return await (start(update, context) if stripped == '\\start' else new_command(update, context))

    last_question_id = session.get('last_question_message_id')
    if last_question_id:
        await clear_reply_markup_by_message(context, update.effective_chat.id, last_question_id)

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
    rewrite_applied = False
    if question['key'] in AI_REWRITE_FIELDS and text and text.strip():
        try:
            improved_text = ai.improve_user_text(text, question['key'])
            if improved_text and improved_text.strip():
                rewrite_applied = improved_text.strip() != text.strip()
                text = improved_text
        except Exception as e:
            logger.warning("AI переформулировка недоступна для %s: %s", question['key'], e)

    if section.get('multiple'):
        current_item = session.get('current_item', {})
        current_item[question['key']] = text
        session['current_item'] = current_item
    else:
        session[question['key']] = text

    if not session.get('editing_mode'):
        session['history'].append({
            'section': section_key,
            'question': question_idx,
            'value': text
        })

    if session.get('editing_mode'):
        if section_key == 'additional' and question['key'] == session.get('editing_section_id'):
            session['editing_mode'] = False
            session['editing_section_id'] = None
            session['editing_item_index'] = None
            if rewrite_applied:
                await update.message.reply_text(
                    "✍️ <i>Улучшили формулировку для резюме.</i>",
                    parse_mode=ParseMode.HTML
                )
            await update.message.reply_text(
                "<b>Раздел обновлен!</b>",
                parse_mode=ParseMode.HTML
            )
            return await show_sections_editor(update, context)

        session['current_question'] += 1
        if session['current_question'] >= len(questions):
            if section.get('multiple'):
                items_key = _items_key(section_key)
                if items_key not in session:
                    session[items_key] = []

                current_item = session.get('current_item', {})
                if current_item and any(current_item.values()):
                    if session.get('editing_item_index') is not None:
                        session[items_key][session['editing_item_index']] = current_item
                    else:
                        session[items_key].append(current_item)
                    if section_key == 'education':
                        _sync_primary_education_from_list(session)
                    session['current_item'] = {}

            session['editing_mode'] = False
            session['editing_section_id'] = None
            session['editing_item_index'] = None

            if rewrite_applied:
                await update.message.reply_text(
                    "✍️ <i>Улучшили формулировку для резюме.</i>",
                    parse_mode=ParseMode.HTML
                )
            await update.message.reply_text(
                "<b>Раздел обновлен!</b>",
                parse_mode=ParseMode.HTML
            )
            return await show_sections_editor(update, context)
        else:
            await ask_current_question(update, context)
            return COLLECTING_DATA

    session['current_question'] += 1
    await ask_current_question(update, context)

    return COLLECTING_DATA


async def skip_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    session = get_user_session(user_id)
    await clear_reply_markup_from_query(query)

    section_key = session['current_section']
    section = config.QUESTIONS_STRUCTURE.get(section_key)
    if section_key == 'education' and session['current_question'] == 0:
        return await next_section(update, context)

    if session.get('editing_mode'):
        section_data = config.QUESTIONS_STRUCTURE.get(section_key)
        questions = section_data['questions'] if section_data else []
        question_idx = session['current_question']
        if section_key == 'additional' and question_idx < len(questions):
            question = questions[question_idx]
            if question['key'] == session.get('editing_section_id'):
                session['editing_mode'] = False
                session['editing_section_id'] = None
                session['editing_item_index'] = None
                await query.message.reply_text(
                    "<b>Раздел обновлен!</b>",
                    parse_mode=ParseMode.HTML
                )
                return await show_sections_editor(update, context)
        if section_key == session.get('editing_section_id'):
            session['editing_mode'] = False
            session['editing_section_id'] = None
            session['editing_item_index'] = None
            await query.message.reply_text(
                "<b>Раздел обновлен!</b>",
                parse_mode=ParseMode.HTML
            )
            return await show_sections_editor(update, context)

    if section and section.get('multiple') and session['current_question'] == 0:
        return await next_section(update, context)

    session['current_question'] += 1
    await ask_current_question(update, context)

    return COLLECTING_DATA


async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    session = get_user_session(user_id)
    await clear_reply_markup_from_query(query)

    if not session.get('history'):
        await query.message.reply_text("Это первый вопрос!")
        await ask_current_question(update, context)
        return COLLECTING_DATA

    last_state = session['history'].pop()
    session['current_section'] = last_state['section']
    session['current_question'] = last_state['question']

    await query.message.reply_text("<i>◀️ Возвращаемся назад...</i>", parse_mode=ParseMode.HTML)
    await ask_current_question(update, context)

    return COLLECTING_DATA


async def add_more_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    session = get_user_session(user_id)
    await clear_reply_markup_from_query(query)

    section_key = session['current_section']

    items_key = _items_key(section_key)
    current_item = session.get('current_item', {})
    if current_item and any(current_item.values()):
        if items_key not in session:
            session[items_key] = []
        session[items_key].append(current_item)
        if section_key == 'education':
            _sync_primary_education_from_list(session)
        logger.info(f"Saved to {items_key}: {current_item}")

    session['current_item'] = {}
    session['current_question'] = 0

    await query.message.reply_text(
        "<b>➕ Добавляем еще одну запись</b>",
        parse_mode=ParseMode.HTML
    )
    await ask_current_question(update, context)

    return COLLECTING_DATA


async def next_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query if update.callback_query else None
    user_id = update.effective_user.id if query else update.message.from_user.id
    session = get_user_session(user_id)

    if query:
        await clear_reply_markup_from_query(query)

    if session.get('editing_mode'):
        session['editing_mode'] = False
        session['editing_section_id'] = None
        session['editing_item_index'] = None
        if query:
            await query.message.reply_text(
                "<b>Раздел обновлен!</b>",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                "<b>Раздел обновлен!</b>",
                parse_mode=ParseMode.HTML
            )
        return await show_sections_editor(update, context)

    if session.get('current_item'):
        section_key = session['current_section']
        items_key = _items_key(section_key)

        current_item = session['current_item']
        if any(current_item.values()):
            if items_key not in session:
                session[items_key] = []
            session[items_key].append(current_item)
            if section_key == 'education':
                _sync_primary_education_from_list(session)
            logger.info(f"Saved in next_section to {items_key}: {current_item}")

        session['current_item'] = {}

    sections_order = ['personal', 'education', 'experience', 'projects', 'skills', 'additional']
    current_idx = sections_order.index(session['current_section']) if session[
                                                                          'current_section'] in sections_order else -1

    if current_idx < len(sections_order) - 1:
        session['current_section'] = sections_order[current_idx + 1]
        session['current_question'] = 0
        await ask_current_question(update, context)
        return COLLECTING_DATA
    else:
        return await request_vacancy(update, context)


async def request_vacancy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query if update.callback_query else None
    user_id = update.effective_user.id if query else update.message.from_user.id
    session = get_user_session(user_id)

    session['waiting_for'] = 'vacancy'

    msg = """<b>Отлично! Базовая информация собрана</b>

📋 Теперь пришли мне <b>текст или ссылку на вакансию</b>, на которую хочешь откликнуться.

🤖 Я проанализирую требования с помощью AI и выделю ключевые слова для твоего резюме!"""

    if query:
        await query.message.reply_text(msg, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    return VACANCY_INPUT


async def process_vacancy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    session = get_user_session(user_id)
    vacancy_input = (update.message.text or '').strip()
    vacancy_text = vacancy_input
    vacancy_url = _extract_first_url(vacancy_input)

    session['waiting_for'] = None

    analyzing_msg = await update.message.reply_text(
        "⏳ <b>Пожалуйста, подождите, анализирую вакансию...</b>",
        parse_mode=ParseMode.HTML
    )

    session['vacancy_url'] = vacancy_url or ''

    if vacancy_url:
        extracted_text, _fetch_error = await asyncio.to_thread(_fetch_vacancy_text_from_url, vacancy_url)
        if not extracted_text:
            try:
                await analyzing_msg.delete()
            except Exception:
                pass
            session['waiting_for'] = 'vacancy'
            await update.message.reply_text(
                "Не удалось получить описание по ссылке.\n\n"
                "Пришли, пожалуйста, текст вакансии сообщением.",
                parse_mode=ParseMode.HTML
            )
            return VACANCY_INPUT

        vacancy_text = extracted_text

    session['vacancy_text'] = vacancy_text
    try:
        keywords = ai.extract_keywords_from_vacancy(vacancy_text)
        session['vacancy_keywords'] = keywords

        await analyzing_msg.delete()

        result_msg = ai.format_keywords_message(keywords)
        await update.message.reply_text(result_msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        await analyzing_msg.delete()
        logger.error("Vacancy analysis error: %s", e)
        keywords = ai._fallback_extraction(vacancy_text)
        session['vacancy_keywords'] = keywords
        result_msg = ai.format_keywords_message(keywords)
        await update.message.reply_text(result_msg, parse_mode=ParseMode.HTML)

    session['template'] = 'Современный'
    session['template_id'] = 'modern'

    msg = """<b>📝 Структура резюме</b>

Сейчас ты можешь изменить структуру резюме:
- Отредактировать разделы
- Удалить ненужные
- Добавить пропущенные

Когда все будет готово, нажми "Готово, создать резюме" """

    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    return await show_sections_editor(update, context)


async def show_sections_editor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query if update.callback_query else None
    user_id = update.effective_user.id if query else update.message.from_user.id
    session = get_user_session(user_id)

    msg = "<b>Редактирование разделов резюме</b>\n\n"
    def is_filled(value):
        if isinstance(value, list):
            return len(value) > 0
        if isinstance(value, str):
            return bool(value.strip())
        return bool(value)

    user_sections = {
        'education': is_filled(session.get('educations')) or is_filled(session.get('university')),
        'experience': is_filled(session.get('experiences')),
        'projects': is_filled(session.get('projects')),
        'skills': is_filled(session.get('technical_skills')),
        'achievements': is_filled(session.get('achievements')),
        'languages': is_filled(session.get('languages')),
        'interests': is_filled(session.get('interests'))
    }
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
    query = update.callback_query
    user_id = update.effective_user.id
    session = get_user_session(user_id)

    await clear_reply_markup_from_query(query)
    current_data = []
    if section_id == 'education':
        educations = session.get('educations', [])
        if educations:
            for i, edu in enumerate(educations, 1):
                current_data.append(f"\n{i}. 🎓 {edu.get('university', '')}")
                current_data.append(f"   Специальность: {edu.get('degree', '')}")
                current_data.append(f"   Период: {edu.get('study_period', '')}")
        elif session.get('university'):
            current_data.append(f"🎓 {session.get('university')}")
            current_data.append(f"   Специальность: {session.get('degree')}")
            current_data.append(f"   Период: {session.get('study_period')}")
    elif section_id == 'experience':
        for i, exp in enumerate(session.get('experiences', []), 1):
            current_data.append(f"\n{i}. 💼 {exp.get('position')}")
            current_data.append(f"   {exp.get('company')} | {exp.get('work_period')}")
            resp = exp.get('responsibilities', '')[:100]
            current_data.append(f"   {resp}...")
    elif section_id == 'projects':
        for i, proj in enumerate(session.get('projects', []), 1):
            current_data.append(f"\n{i}. {proj.get('project_name')}")
            desc = proj.get('project_description', '')[:100]
            current_data.append(f"   {desc}...")
    elif section_id == 'skills':
        current_data.append(f"💻 {session.get('technical_skills', '')}")
        if session.get('soft_skills'):
            current_data.append(f"🤝 {session.get('soft_skills', '')}")
    elif section_id == 'achievements':
        ach = session.get('achievements', '')
        if ach:
            for line in ach.split('\n')[:3]:
                if line.strip():
                    current_data.append(f"🏆 {line.strip()}")
    elif section_id == 'languages':
        current_data.append(f"🌍 {session.get('languages', '')}")
    elif section_id == 'interests':
        current_data.append(f"🎯 {session.get('interests', '')}")

    msg = "<b>✏️ Редактирование раздела</b>\n\n"
    if current_data:
        msg += "<b>📋 Текущие данные:</b>\n"
        msg += "\n".join(current_data)
        msg += "\n\n"
    msg += "<i>Отправь новые данные для замены или нажми Пропустить для сохранения текущих</i>"
    session['editing_mode'] = True
    session['editing_section_id'] = section_id
    session['editing_complete_after'] = section_id

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
        session['current_item'] = {}
        if section_key == 'education':
            session['educations'] = []
            _sync_primary_education_from_list(session)

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
    query = update.callback_query
    user_id = update.effective_user.id
    session = get_user_session(user_id)
    await clear_reply_markup_from_query(query)
    section_keys_map = {
        'education': ['university', 'degree', 'study_period', 'educations', 'gpa'],
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
            session[key] = [] if key in ['educations', 'experiences', 'projects'] else ''
    if section_id == 'education':
        _sync_primary_education_from_list(session)

    await query.message.reply_text(
        f"<b>🗑 Раздел удален</b>",
        parse_mode=ParseMode.HTML
    )

    return await show_sections_editor(update, context)


async def add_section(update: Update, context: ContextTypes.DEFAULT_TYPE, section_id):
    return await edit_section(update, context, section_id)


async def finalize_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    username = update.effective_user.username
    session = get_user_session(user_id)
    await clear_reply_markup_from_query(query)

    creating_msg = await query.message.reply_text(
        "⏳ <b>Создаю твое резюме...</b>\nЭто займет до 2 минут.",
        parse_mode=ParseMode.HTML
    )
    session['status'] = 'completed'
    session['resume_date'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    save_ok = db.save_user_data(user_id, username, session)
    if not save_ok:
        logger.warning("Не удалось сохранить данные пользователя %s перед генерацией", user_id)

    pdf_data, error = latex_gen.generate_pdf(session, session.get('vacancy_keywords'))

    await creating_msg.delete()

    if pdf_data:
        caption = "<b>Твое резюме готово!</b>"

        await query.message.reply_document(
            document=pdf_data,
            filename=f"Resume_{session.get('full_name', 'User').replace(' ', '_')}.pdf",
            caption=caption,
            parse_mode=ParseMode.HTML
        )
    else:
        latex_code = latex_gen.generate_resume(session, session.get('vacancy_keywords'))
        latex_file = io.BytesIO(latex_code.encode('utf-8'))

        caption = """<b>Твое резюме готово!</b>

<b>Как получить PDF:</b>
1. Открой файл в Overleaf (overleaf.com)
2. Нажми Recompile
3. Скачай PDF

<i>Отправляю в формате .tex</i>"""

        await query.message.reply_document(
            document=latex_file,
            filename=f"Resume_{session.get('full_name', 'User').replace(' ', '_')}.tex",
            caption=caption,
            parse_mode=ParseMode.HTML
        )

    if 'resumes' not in session:
        session['resumes'] = []
    session['resumes'].append({
        'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'name': session.get('full_name', 'Резюме'),
        'template': session.get('template', 'Modern')
    })

    if not save_ok:
        await query.message.reply_text(
            "Не удалось сохранить данные в таблицу с первого раза. Попробую повторно в фоне.",
            parse_mode=ParseMode.HTML
        )
        db.save_user_data(user_id, username, session)

    return await start_feedback(update, context)


async def start_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    user_id = update.effective_user.id if update.callback_query else update.message.from_user.id
    session = get_user_session(user_id)

    idx = session.get('feedback_question', 0)

    if idx >= len(config.FEEDBACK_QUESTIONS):
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
    query = update.callback_query
    user_id = update.effective_user.id
    session = get_user_session(user_id)
    await clear_reply_markup_from_query(query)

    idx = session.get('feedback_question', 0)
    question = config.FEEDBACK_QUESTIONS[idx]

    session['feedback'][question['key']] = rating
    session['feedback_question'] += 1

    await query.message.reply_text(f"Оценка: {rating}", parse_mode=ParseMode.HTML)
    await ask_feedback_question(update, context)

    return FEEDBACK_COLLECT


async def save_time(update: Update, context: ContextTypes.DEFAULT_TYPE, time_code):
    query = update.callback_query
    user_id = update.effective_user.id
    session = get_user_session(user_id)
    await clear_reply_markup_from_query(query)

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

    await query.message.reply_text(f"Время: {time_map.get(time_code)}", parse_mode=ParseMode.HTML)
    await ask_feedback_question(update, context)

    return FEEDBACK_COLLECT


async def process_answer(update: Update, context: ContextTypes.DEFAULT_TYPE, answer):
    query = update.callback_query
    user_id = update.effective_user.id
    session = get_user_session(user_id)
    await clear_reply_markup_from_query(query)

    idx = session.get('feedback_question', 0)
    question = config.FEEDBACK_QUESTIONS[idx]

    answer_text = 'Да' if answer == 'yes' else 'Нет'
    session['feedback'][question['key']] = answer_text
    session['feedback_question'] += 1
    await query.message.reply_text(f"Ответ: {answer_text}", parse_mode=ParseMode.HTML)
    await ask_feedback_question(update, context)

    return FEEDBACK_COLLECT


async def finish_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.callback_query else update.message.from_user.id
    username = update.effective_user.username if update.callback_query else update.message.from_user.username
    session = get_user_session(user_id)
    db.save_feedback(user_id, username, session.get('feedback', {}))

    try:
        db.update_analytics()
    except Exception as e:
        logger.error(f"Analytics error: {e}")

    msg = """<b>Спасибо за участие в исследовании!</b>

Твои ответы очень помогут нам улучшить продукт.

Удачи в поиске работы! """

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
    help_text = """<b>Помощь по боту</b>

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
- Бот анализирует вакансию и выделяет ключевые слова

<b>🎯 О боте:</b>
Прототип для UX-исследования по упрощению создания резюме для студентов и молодых специалистов."""

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                help_text,
                reply_markup=kb.main_menu(),
                parse_mode=ParseMode.HTML
            )
        except BadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                raise
    else:
        await update.message.reply_text(
            help_text,
            reply_markup=kb.main_menu(),
            parse_mode=ParseMode.HTML
        )

    return MENU


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "Действие отменено. Используй /start для начала",
        reply_markup=kb.main_menu(),
        parse_mode=ParseMode.HTML
    )
    return MENU


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    session = get_user_session(user_id)
    session['username'] = update.effective_user.username
    _reset_resume_data(session)
    session['current_section'] = 'personal'
    session['current_question'] = 0
    session['history'] = []

    msg = "<b>📝 Начинаем создание нового резюме!</b>\n\nПоехали! "
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    await ask_current_question(update, context)
    return COLLECTING_DATA


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Произошла ошибка. Попробуй еще раз или напиши /start",
                parse_mode=ParseMode.HTML
            )
        except:
            pass


async def process_feedback_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    session = get_user_session(user_id)

    if session['feedback'].get('comment_requested'):
        session['feedback']['comment'] = update.message.text
        await update.message.reply_text("Спасибо за комментарий!", parse_mode=ParseMode.HTML)
        return await finish_feedback(update, context)

    return FEEDBACK_COLLECT


async def feedback_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await start_feedback(update, context)


def main():
    application = Application.builder().token(config.TELEGRAM_TOKEN).build()
    application.add_error_handler(error_handler)
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CommandHandler('new', new_command)
        ],
        states={
            MENU: [
                CallbackQueryHandler(button_handler),
                CommandHandler('start', start),
                CommandHandler('new', new_command),
                CommandHandler('help', help_command),
                CommandHandler('feedback', start_feedback)
            ],
            COLLECTING_DATA: [
                CommandHandler('start', start),
                CommandHandler('new', new_command),
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_text_answer),
                CallbackQueryHandler(button_handler)
            ],
            VACANCY_INPUT: [
                CommandHandler('start', start),
                CommandHandler('new', new_command),
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_vacancy),
                CallbackQueryHandler(button_handler)
            ],
            TEMPLATE_SELECT: [
                CommandHandler('start', start),
                CommandHandler('new', new_command),
                CallbackQueryHandler(button_handler)
            ],
            EDIT_SECTIONS: [
                CommandHandler('start', start),
                CommandHandler('new', new_command),
                CallbackQueryHandler(button_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_text_answer)
            ],
            FEEDBACK_COLLECT: [
                CommandHandler('start', start),
                CommandHandler('new', new_command),
                CallbackQueryHandler(button_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_feedback_comment)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True,
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
        drop_pending_updates=True
    )


def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        httpd.serve_forever()


if __name__ == '__main__':
    threading.Thread(target=run_dummy_server, daemon=True).start()
    main()
