import re

# Пытаемся импортировать Google Gemini
try:
    import google.generativeai as genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ Google Gemini недоступен - используется fallback анализ")

import config


class AIAnalyzer:
    def __init__(self):
        self.model = None

        if GEMINI_AVAILABLE and config.GOOGLE_API_KEY:
            try:
                genai.configure(api_key=config.GOOGLE_API_KEY)
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                print("✅ Google Gemini подключен")
            except Exception as e:
                print(f"⚠️ Ошибка подключения Gemini: {e}")
                print("Используется fallback анализ")
        else:
            print("⚠️ Используется fallback анализ вакансий")

    def extract_keywords_from_vacancy(self, vacancy_text):
        """Извлечение ключевых слов из вакансии"""
        if self.model:
            try:
                return self._gemini_extraction(vacancy_text)
            except Exception as e:
                print(f"Ошибка Gemini API: {e}")
                return self._fallback_extraction(vacancy_text)
        else:
            return self._fallback_extraction(vacancy_text)

    def _gemini_extraction(self, vacancy_text):
        """Извлечение с помощью Gemini"""
        prompt = f"""Проанализируй текст вакансии и ТОЧНО выдели упомянутые технологии и навыки.

ВАЖНО: 
- Выписывай ТОЛЬКО те технологии, которые ЯВНО упомянуты в тексте
- НЕ добавляй технологии, которых нет в тексте
- Сохраняй точные названия (Rust, C++, PostgreSQL, Clickhouse и т.д.)

Вакансия:
{vacancy_text}

Ответ дай строго в формате:

ТЕХНИЧЕСКИЕ НАВЫКИ:
- навык1
- навык2

SOFT SKILLS:
- навык1
- навык2

КЛЮЧЕВЫЕ СЛОВА:
- слово1
- слово2"""

        response = self.model.generate_content(prompt)
        return self._parse_ai_response(response.text, vacancy_text)

    def _parse_ai_response(self, text, original_vacancy):
        """Парсинг ответа AI с проверкой"""
        result = {
            'technical': [],
            'soft': [],
            'keywords': []
        }

        current_section = None
        for line in text.split('\n'):
            line = line.strip()
            if 'ТЕХНИЧЕСКИЕ НАВЫКИ' in line.upper() or 'TECHNICAL' in line.upper():
                current_section = 'technical'
            elif 'SOFT SKILLS' in line.upper():
                current_section = 'soft'
            elif 'КЛЮЧЕВЫЕ СЛОВА' in line.upper() or 'KEYWORDS' in line.upper():
                current_section = 'keywords'
            elif line.startswith('-') and current_section:
                skill = line[1:].strip()
                if skill and self._verify_in_text(skill, original_vacancy):
                    result[current_section].append(skill)

        # Если не распарсилось - используем fallback
        if not any(result.values()):
            return self._fallback_extraction(original_vacancy)

        return result

    def _verify_in_text(self, skill, text):
        """Проверка что навык действительно есть в тексте"""
        return skill.lower() in text.lower()

    def _fallback_extraction(self, text):
        """Улучшенная экстракция без AI"""
        text_lower = text.lower()

        # Максимально расширенный список
        technical_skills = {
            # Программирование
            'Python', 'JavaScript', 'Java', 'C++', 'C#', 'C', 'TypeScript', 'Go', 'Rust',
            'Ruby', 'PHP', 'Swift', 'Kotlin', 'Scala', 'R', 'MATLAB', 'Dart', 'Lua',

            # Фреймворки
            'React', 'Vue', 'Angular', 'Django', 'Flask', 'FastAPI', 'Spring',
            'Node.js', 'Express', 'Next.js', 'Laravel', 'Rails', 'Tokio', 'Actix',

            # Базы данных
            'PostgreSQL', 'MySQL', 'MongoDB', 'Redis', 'Elasticsearch', 'Clickhouse',
            'Kafka', 'RabbitMQ',

            # DevOps
            'Docker', 'Kubernetes', 'Git', 'GitLab', 'GitHub', 'Jenkins', 'CI/CD',
            'AWS', 'Azure', 'GCP', 'Terraform', 'Ansible', 'Linux',

            # Дизайн и CAD
            'AutoCAD', 'Photoshop', 'Illustrator', 'Figma', 'Sketch', 'Adobe XD',
            'InDesign', 'Blender', '3ds Max', 'Maya', 'SketchUp', 'Revit',
            'ArchiCAD', 'SolidWorks', 'CATIA', 'Procreate', 'After Effects',
            'Premiere Pro', 'Lightroom', 'CorelDRAW', 'Affinity Designer',

            # Другое
            'REST API', 'GraphQL', 'Microservices', 'Machine Learning',
            'Data Science', 'Excel', 'Power BI', 'Tableau', 'SAP', 'Unity',
            'VR', 'AR', '3D моделирование', 'рендеринг', 'визуализация'
        }

        # Расширенные soft skills + специфичные для дизайна
        soft_skills = {
            'коммуникация', 'communication', 'работа в команде', 'teamwork',
            'лидерство', 'leadership', 'problem solving', 'аналитическое мышление',
            'креативность', 'creativity', 'внимание к деталям', 'attention to detail',
            'тайм-менеджмент', 'time management', 'презентации', 'presentation',
            'английский', 'english', 'стрессоустойчивость', 'stress resistance',
            'переговоры', 'negotiations', 'продажи', 'sales',
            'клиентоориентированность', 'работа с клиентами',
            'авторский надзор', 'ведение проекта', 'комплектация',
            'консультирование', 'курирование', 'координация'
        }

        # Поиск навыков
        found_technical = []
        found_soft = []

        for skill in technical_skills:
            pattern = r'\b' + re.escape(skill.lower()) + r'\b'
            if re.search(pattern, text_lower):
                found_technical.append(skill)

        for skill in soft_skills:
            if skill.lower() in text_lower:
                found_soft.append(skill)

        # Специальные паттерны для дизайна интерьера
        if 'дизайн' in text_lower and 'интерьер' in text_lower:
            if 'AutoCAD' not in found_technical:
                found_technical.insert(0, 'AutoCAD')
            if 'Photoshop' not in found_technical:
                found_technical.insert(1, 'Photoshop')
            if 'работа с клиентами' not in found_soft:
                found_soft.append('работа с клиентами')
            if 'креативность' not in found_soft:
                found_soft.append('креативность')

        found_technical = list(dict.fromkeys(found_technical))[:15]
        found_soft = list(dict.fromkeys(found_soft))[:8]
        found_keywords = list(dict.fromkeys(found_technical + found_soft[:3]))[:20]

        return {
            'technical': found_technical,
            'soft': found_soft,
            'keywords': found_keywords
        }

    def format_keywords_message(self, keywords_dict):
        """Форматирование сообщения"""
        msg = "<b>🔍 Анализ вакансии завершен!</b>\n\n"

        if keywords_dict.get('technical'):
            msg += "<b>💻 Технические навыки:</b>\n"
            for skill in keywords_dict['technical']:
                msg += f"  • {skill}\n"
            msg += "\n"

        if keywords_dict.get('soft'):
            msg += "<b>🤝 Soft skills:</b>\n"
            for skill in keywords_dict['soft']:
                msg += f"  • {skill}\n"
            msg += "\n"

        if keywords_dict.get('keywords'):
            msg += "<b>🎯 Ключевые слова для ATS:</b>\n"
            msg += ", ".join(keywords_dict['keywords'][:10])
            msg += "\n\n"

        msg += "💡 <i>Эти слова будут выделены в вашем резюме!</i>"

        return msg