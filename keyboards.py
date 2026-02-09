from telegram import InlineKeyboardButton, InlineKeyboardMarkup


class Keyboards:
    @staticmethod
    def yes_no_skip():
        """Да/Нет/Пропустить"""
        keyboard = [
            [InlineKeyboardButton("✅ Да", callback_data="answer_yes")],
            [InlineKeyboardButton("❌ Нет", callback_data="answer_no")],
            [InlineKeyboardButton("⏭ Пропустить", callback_data="answer_skip")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def yes_no():
        """Да/Нет"""
        keyboard = [
            [InlineKeyboardButton("✅ Да", callback_data="answer_yes")],
            [InlineKeyboardButton("❌ Нет", callback_data="answer_no")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def skip_back():
        """Пропустить/Назад"""
        keyboard = [
            [InlineKeyboardButton("⏭ Пропустить", callback_data="skip")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def add_more_back():
        """Добавить еще/Продолжить/Назад"""
        keyboard = [
            [InlineKeyboardButton("➕ Добавить еще", callback_data="add_more")],
            [InlineKeyboardButton("▶️ Продолжить", callback_data="continue")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def sections_edit(user_sections):
        """Редактирование разделов"""
        keyboard = []
        sections_map = {
            'education': 'Образование',
            'experience': 'Опыт работы',
            'projects': 'Проекты',
            'skills': 'Навыки',
            'achievements': 'Достижения',
            'languages': 'Языки',
            'interests': 'Интересы'
        }

        for section_id, section_name in sections_map.items():
            if section_id in user_sections and user_sections[section_id]:
                # Раздел заполнен - можно редактировать или удалить
                keyboard.append([
                    InlineKeyboardButton(
                        f"✏️ {section_name}",
                        callback_data=f"edit_{section_id}"
                    ),
                    InlineKeyboardButton(
                        "🗑",
                        callback_data=f"delete_{section_id}"
                    )
                ])
            else:
                # Раздел пропущен - можно добавить
                keyboard.append([
                    InlineKeyboardButton(
                        f"➕ {section_name}",
                        callback_data=f"add_{section_id}"
                    )
                ])

        keyboard.append([InlineKeyboardButton("✅ Готово, создать резюме", callback_data="finalize")])
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def rating(max_rating=5):
        """Оценка по шкале"""
        keyboard = []
        row = []
        for i in range(1, max_rating + 1):
            row.append(InlineKeyboardButton(str(i), callback_data=f"rating_{i}"))
        keyboard.append(row)
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def time_options():
        """Варианты времени"""
        keyboard = [
            [InlineKeyboardButton("⏱ Менее 15 минут", callback_data="time_15")],
            [InlineKeyboardButton("⏱ 15-30 минут", callback_data="time_30")],
            [InlineKeyboardButton("⏱ 30-60 минут", callback_data="time_60")],
            [InlineKeyboardButton("⏱ Больше часа", callback_data="time_60plus")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def main_menu():
        """Главное меню"""
        keyboard = [
            [InlineKeyboardButton("🆕 Создать новое резюме", callback_data="new_resume")],
            [InlineKeyboardButton("📄 Мои резюме", callback_data="my_resumes")],
            [InlineKeyboardButton("💭 Оставить отзыв", callback_data="feedback")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def resume_list(resumes):
        """Список резюме для выбора"""
        keyboard = []
        for idx, resume in enumerate(resumes):
            keyboard.append([
                InlineKeyboardButton(
                    f"📄 {resume['name']} ({resume['date']})",
                    callback_data=f"view_resume_{idx}"
                )
            ])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")])
        return InlineKeyboardMarkup(keyboard)