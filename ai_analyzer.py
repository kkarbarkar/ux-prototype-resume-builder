import logging
import os
import re

try:
    import google.generativeai as genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("Google Gemini недоступен - используется fallback анализ")

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
                available_models = self._get_available_models()
                if available_models:
                    normalized = [self._normalize_model_name(name) for name in available_models]
                    unique_normalized = []
                    for name in normalized:
                        if name not in unique_normalized:
                            unique_normalized.append(name)
                    filtered_models = [
                        name for name in unique_normalized if self._is_supported_model_name(name)
                    ]
                    if preferred in filtered_models:
                        self.model_candidates = [preferred] + [
                            name for name in filtered_models if name != preferred
                        ]
                    else:
                        self.model_candidates = filtered_models
                else:
                    fallback_candidates = [
                        preferred,
                        'gemini-1.5-flash',
                        'gemini-1.5-pro',
                        'gemini-1.0-pro',
                        'gemini-pro'
                    ]
                    self.model_candidates = []
                    for name in fallback_candidates:
                        if name not in self.model_candidates and self._is_supported_model_name(name):
                            self.model_candidates.append(name)
                if not self.model_candidates:
                    self.model_candidates = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
                self.model_name = self.model_candidates[0]
                self.model = genai.GenerativeModel(self.model_name)
                self.logger.info("Google Gemini подключен: %s", self.model_name)
            except Exception as e:
                self.logger.warning("Ошибка подключения Gemini: %s", e)
                self.logger.info("Используется fallback анализ")
        else:
            self.logger.info("Используется fallback анализ вакансий")

    def extract_keywords_from_vacancy(self, vacancy_text):
        if self.model:
            try:
                return self._gemini_extraction(vacancy_text)
            except Exception as e:
                print(f"Ошибка Gemini API: {e}")
                return self._fallback_extraction(vacancy_text)
        else:
            return self._fallback_extraction(vacancy_text)

    def improve_user_text(self, text, field_key=''):
        raw_text = (text or '').strip()
        if not raw_text:
            return text

        if not self.model:
            return self._fallback_rephrase(raw_text, field_key)

        prompt = f"""Ты — редактор резюме. Улучши формулировку текста для раздела "{field_key}".

Правила:
- Не выдумывай факты, цифры, компании и технологии.
- Сохрани исходный язык (русский/английский).
- Сделай формулировки короче, профессиональнее и конкретнее.
- Если в тексте несколько строк, верни несколько строк в том же формате.
- Верни только итоговый текст без пояснений.

Текст:
{raw_text}"""

        attempts = max(1, len(self.model_candidates))
        last_error = None
        for _ in range(attempts):
            try:
                response = self.model.generate_content(prompt)
                rewritten = (getattr(response, 'text', None) or '').strip()
                if rewritten:
                    return rewritten
                return self._fallback_rephrase(raw_text, field_key)
            except Exception as e:
                last_error = e
                if self._should_rotate_model(str(e)) and self._rotate_model(disable_current=True):
                    continue
                break

        if last_error:
            self.logger.warning("Не удалось переформулировать текст через Gemini: %s", last_error)
        return self._fallback_rephrase(raw_text, field_key)

    def _fallback_rephrase(self, text, field_key=''):
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not lines:
            return text

        if field_key in {'responsibilities', 'project_description', 'achievements'}:
            normalized = []
            for line in lines:
                cleaned = line.lstrip('-•').strip()
                if not cleaned:
                    continue
                if cleaned[-1] in '.;,':
                    cleaned = cleaned[:-1]
                if cleaned and cleaned[0].islower():
                    cleaned = cleaned[0].upper() + cleaned[1:]
                normalized.append(cleaned)
            return '\n'.join(normalized) if normalized else text

        cleaned = ' '.join(lines).strip()
        if cleaned and cleaned[0].islower():
            cleaned = cleaned[0].upper() + cleaned[1:]
        return cleaned or text

    def _gemini_extraction(self, vacancy_text):
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

        attempts = max(1, len(self.model_candidates))
        last_error = None
        for _ in range(attempts):
            try:
                response = self.model.generate_content(prompt)
                return self._parse_ai_response(response.text, vacancy_text)
            except Exception as e:
                last_error = e
                error_text = str(e)
                if self._should_rotate_model(error_text):
                    if self._rotate_model(disable_current=True):
                        continue
                raise
        if last_error:
            raise last_error
        raise RuntimeError("Gemini extraction failed without explicit exception")

    def _should_rotate_model(self, error_text):
        return 'not found' in error_text.lower() or '404' in error_text

    def _rotate_model(self, disable_current=False):
        if not self.model_candidates:
            return False
        if disable_current and self.model_name in self.model_candidates:
            self.model_candidates = [name for name in self.model_candidates if name != self.model_name]
            if not self.model_candidates:
                return False
            self.model_index = 0
        else:
            self.model_index += 1
            if self.model_index >= len(self.model_candidates):
                self.model_index = 0
        self.model_name = self.model_candidates[self.model_index]
        self.model = genai.GenerativeModel(self.model_name)
        self.logger.warning("Переключаю модель Gemini на %s", self.model_name)
        return True

    def _normalize_model_name(self, name):
        if name.startswith('models/'):
            return name[len('models/'):]
        return name

    def _is_supported_model_name(self, name):
        lowered = name.lower()
        return not lowered.endswith('-latest')

    def _get_available_models(self):
        try:
            models = []
            for model in genai.list_models():
                methods = getattr(model, 'supported_generation_methods', None)
                if methods is None:
                    methods = getattr(model, 'supportedGenerationMethods', None)
                methods = methods or []
                if any('generatecontent' in method.lower() for method in methods):
                    name = getattr(model, 'name', None)
                    if name:
                        models.append(name)
            return models
        except Exception as e:
            self.logger.warning("Не удалось получить список моделей Gemini: %s", e)
            return []

    def _parse_ai_response(self, text, original_vacancy):
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

        if not any(result.values()):
            return self._fallback_extraction(original_vacancy)

        return result

    def _verify_in_text(self, skill, text):
        return skill.lower() in text.lower()

    def _fallback_extraction(self, text):
        text_lower = text.lower()

        key_skills = self._extract_key_skills(text)

        technical_skills = {
            'Python', 'JavaScript', 'Java', 'C++', 'C\\+\\+', 'Cpp', 'C#', 'C Sharp', 'C',
            'TypeScript', 'Go', 'Golang', 'Rust',
            'Ruby', 'PHP', 'Swift', 'Kotlin', 'Scala', 'R', 'MATLAB', 'Dart', 'Lua',
            'React', 'Vue', 'Angular', 'Django', 'Flask', 'FastAPI', 'Spring',
            'Node.js', 'Express', 'Next.js', 'Laravel', 'Rails', 'Tokio', 'Actix',
            'PostgreSQL', 'MySQL', 'MongoDB', 'Redis', 'Elasticsearch', 'Clickhouse',
            'Kafka', 'RabbitMQ', 'MS SQL', 'MSSQL', 'BigQuery', 'SQL', 'NoSQL',
            'Docker', 'Kubernetes', 'Git', 'GitLab', 'GitHub', 'Jenkins', 'CI/CD',
            'AWS', 'Azure', 'GCP', 'Terraform', 'Ansible', 'Linux',
            'pandas', 'numpy', 'requests', 'asyncio',
            'ETL', 'ELT',
            'API', 'REST', 'REST API',
            'bash',
            'mavsdk', 'opencv', 'OpenCV', 'ardupilot', 'ArduPilot',
            'Raspberry Pi', 'Orange Pi', 'Nvidia Jetson', 'Jetson',
            'AutoCAD', 'Photoshop', 'Illustrator', 'Figma', 'Sketch', 'Adobe XD',
            'REST API', 'GraphQL', 'Microservices', 'Machine Learning',
            'нейронные сети', 'нейросети', 'криптография'
        }
        if 'c++' in text_lower or 'cpp' in text_lower or 'c\\+\\+' in text_lower:
            found_technical = ['C++']
        else:
            found_technical = []

        for skill in technical_skills:
            if skill == 'C++' or skill == 'C\\+\\+' or skill == 'Cpp':
                continue

            if skill in ['C', 'R']:
                pattern = r'\b' + re.escape(skill) + r'\b'
                if re.search(pattern, text, re.IGNORECASE):
                    if skill not in found_technical:
                        found_technical.append(skill)
            else:
                pattern = r'\b' + re.escape(skill.lower()) + r'\b'
                if re.search(pattern, text_lower):
                    if skill not in found_technical:
                        found_technical.append(skill)

        soft_skills_list = [
            'коммуникация', 'работа в команде', 'teamwork',
            'лидерство', 'leadership', 'problem solving',
            'параллельные вычисления', 'асинхронные вычисления'
        ]

        found_soft = [s for s in soft_skills_list if s.lower() in text_lower]

        if key_skills:
            for ks in key_skills:
                if ks not in found_technical:
                    found_technical.insert(0, ks)

        found_technical = list(dict.fromkeys(found_technical))[:20]
        found_soft = list(dict.fromkeys(found_soft))[:8]
        found_keywords = list(dict.fromkeys(key_skills + found_technical + found_soft[:3]))[:25]

        return {
            'technical': found_technical,
            'soft': found_soft,
            'keywords': found_keywords
        }

    def _extract_key_skills(self, text):
        markers = ['ключевые навыки', 'key skills', 'skills']
        lines = text.splitlines()
        start_idx = None
        for i, line in enumerate(lines):
            if any(m in line.lower() for m in markers):
                start_idx = i + 1
                break
        if start_idx is None:
            return []

        collected = []
        for line in lines[start_idx:]:
            if not line.strip():
                break
            cleaned = line.strip().lstrip('-•').strip()
            if not cleaned:
                continue
            collected.extend([p.strip() for p in re.split(r'[;,]', cleaned) if p.strip()])

        return list(dict.fromkeys(collected))[:15]

    def format_keywords_message(self, keywords_dict):
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
