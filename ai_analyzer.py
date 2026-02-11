import logging
import os
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
        self.model_name = None
        self.model_candidates = []
        self.model_index = 0
        self.logger = logging.getLogger(__name__)

        if GEMINI_AVAILABLE and config.GOOGLE_API_KEY:
            try:
                genai.configure(api_key=config.GOOGLE_API_KEY)
                preferred = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
                self.model_candidates = [
                    preferred,
                    'gemini-1.5-flash-latest',
                    'gemini-1.0-pro',
                    'gemini-pro'
                ]
                self.model_name = self.model_candidates[0]
                self.model = genai.GenerativeModel(self.model_name)
                self.logger.info("✅ Google Gemini подключен: %s", self.model_name)
            except Exception as e:
                self.logger.warning("⚠️ Ошибка подключения Gemini: %s", e)
                self.logger.info("Используется fallback анализ")
        else:
            self.logger.info("⚠️ Используется fallback анализ вакансий")

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

        try:
            response = self.model.generate_content(prompt)
            return self._parse_ai_response(response.text, vacancy_text)
        except Exception as e:
            error_text = str(e)
            if self._should_rotate_model(error_text):
                self._rotate_model()
                response = self.model.generate_content(prompt)
                return self._parse_ai_response(response.text, vacancy_text)
            raise

    def _should_rotate_model(self, error_text):
        return 'not found' in error_text.lower() or '404' in error_text

    def _rotate_model(self):
        if not self.model_candidates:
            return
        self.model_index += 1
        if self.model_index >= len(self.model_candidates):
            self.model_index = 0
        self.model_name = self.model_candidates[self.model_index]
        self.model = genai.GenerativeModel(self.model_name)
        self.logger.warning("🔁 Переключаю модель Gemini на %s", self.model_name)

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

        technical_skills = {
            # Программирование - ВАЖНО: добавляем варианты написания
            'Python', 'JavaScript', 'Java', 'C++', 'C\+\+', 'Cpp', 'C#', 'C Sharp', 'C',
            'TypeScript', 'Go', 'Golang', 'Rust',
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

            # Библиотеки
            'mavsdk', 'opencv', 'OpenCV', 'ardupilot', 'ArduPilot',
            'Raspberry Pi', 'Orange Pi', 'Nvidia Jetson', 'Jetson',

            # Дизайн
            'AutoCAD', 'Photoshop', 'Illustrator', 'Figma', 'Sketch', 'Adobe XD',

            # Другое
            'REST API', 'GraphQL', 'Microservices', 'Machine Learning',
            'нейронные сети', 'нейросети', 'криптография'
        }

        # Специальная обработка для C++
        if 'c++' in text_lower or 'cpp' in text_lower or 'c\+\+' in text_lower:
            found_technical = ['C++']
        else:
            found_technical = []

        # Обычный поиск для остальных
        for skill in technical_skills:
            if skill == 'C++' or skill == 'C\+\+' or skill == 'Cpp':
                continue  # Уже обработали выше

            # Специальная обработка для однобуквенных (C, R)
            if skill in ['C', 'R']:
                # Ищем как отдельное слово
                pattern = r'\b' + re.escape(skill) + r'\b'
                if re.search(pattern, text, re.IGNORECASE):
                    if skill not in found_technical:
                        found_technical.append(skill)
            else:
                pattern = r'\b' + re.escape(skill.lower()) + r'\b'
                if re.search(pattern, text_lower):
                    if skill not in found_technical:
                        found_technical.append(skill)

        # Soft skills
        soft_skills_list = [
            'коммуникация', 'работа в команде', 'teamwork',
            'лидерство', 'leadership', 'problem solving',
            'параллельные вычисления', 'асинхронные вычисления'
        ]

        found_soft = [s for s in soft_skills_list if s.lower() in text_lower]

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
