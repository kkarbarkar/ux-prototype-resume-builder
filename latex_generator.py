import subprocess
import os
import tempfile
from datetime import datetime


class LaTeXGenerator:
    def __init__(self):
        self.template = self._get_template()

    def _get_template(self):
        """Базовый шаблон LaTeX (Jake's Resume)"""
        return r"""\documentclass[letterpaper,11pt]{article}

    \usepackage{latexsym}
    \usepackage[empty]{fullpage}
    \usepackage{titlesec}
    \usepackage{marvosym}
    \usepackage[usenames,dvipsnames]{color}
    \usepackage{verbatim}
    \usepackage{enumitem}
    \usepackage[hidelinks]{hyperref}
    \usepackage{fancyhdr}
    \usepackage[english,russian]{babel}
    \usepackage[utf8]{inputenc}
    \usepackage[T2A]{fontenc}
    \usepackage{tabularx}

    \pagestyle{fancy}
    \fancyhf{}
    \fancyfoot{}
    \renewcommand{\headrulewidth}{0pt}
    \renewcommand{\footrulewidth}{0pt}

    \addtolength{\oddsidemargin}{-0.5in}
    \addtolength{\evensidemargin}{-0.5in}
    \addtolength{\textwidth}{1in}
    \addtolength{\topmargin}{-.5in}
    \addtolength{\textheight}{1.0in}

    \urlstyle{same}
    \raggedbottom
    \raggedright
    \setlength{\tabcolsep}{0in}

    \titleformat{\section}{
      \vspace{-4pt}\scshape\raggedright\large
    }{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]

    \newcommand{\resumeItem}[1]{
      \item\small{
        {#1 \vspace{-2pt}}
      }
    }

    \newcommand{\resumeSubheading}[4]{
      \vspace{-2pt}\item
        \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
          \textbf{#1} & #2 \\
          \textit{\small#3} & \textit{\small #4} \\
        \end{tabular*}\vspace{-7pt}
    }

    \newcommand{\resumeProjectHeading}[2]{
        \item
        \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
          \small#1 & #2 \\
        \end{tabular*}\vspace{-7pt}
    }

    \newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}
    \renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}
    \newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
    \newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
    \newcommand{\resumeItemListStart}{\begin{itemize}}
    \newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}

    \begin{document}

    %----------HEADING----------
    \begin{center}
        \textbf{\Huge \scshape {FULL_NAME}} \\ \vspace{1pt}
        \small {PHONE} $|$ \href{mailto:{EMAIL}}{\underline{{EMAIL}}}{LOCATION_PIPE}{LINKS}
    \end{center}

    {EDUCATION_SECTION}

    {EXPERIENCE_SECTION}

    {PROJECTS_SECTION}

    {SKILLS_SECTION}

    {ACHIEVEMENTS_SECTION}

    {LANGUAGES_SECTION}

    {INTERESTS_SECTION}

    \end{document}
    """

    def generate_resume(self, user_data, keywords=None):
        """Генерация LaTeX кода резюме"""
        latex_content = self.template

        # Личная информация
        latex_content = latex_content.replace('{FULL_NAME}', self._escape_latex(user_data.get('full_name', 'Ваше Имя')))
        email = user_data.get('email', 'email@example.com')
        phone = user_data.get('phone', '+7 999 999-99-99')
        latex_content = latex_content.replace('{EMAIL}', self._escape_latex(email))
        latex_content = latex_content.replace('{PHONE}', self._escape_latex(phone))

        # Локация
        location = user_data.get('location', '')
        if location:
            latex_content = latex_content.replace('{LOCATION_PIPE}', f' $|$ {self._escape_latex(location)}')
        else:
            latex_content = latex_content.replace('{LOCATION_PIPE}', '')

        # Ссылки (LinkedIn, GitHub, Portfolio) - в одну строку
        links = []
        if user_data.get('linkedin'):
            linkedin = user_data.get('linkedin').replace('https://', '').replace('http://', '')
            links.append(r'\href{https://' + self._escape_latex(linkedin) + r'}{\underline{LinkedIn}}')
        if user_data.get('github'):
            github = user_data.get('github').replace('https://', '').replace('http://', '')
            links.append(r'\href{https://' + self._escape_latex(github) + r'}{\underline{GitHub}}')
        if user_data.get('portfolio'):
            portfolio = user_data.get('portfolio').replace('https://', '').replace('http://', '')
            links.append(r'\href{https://' + self._escape_latex(portfolio) + r'}{\underline{Portfolio}}')

        if links:
            latex_content = latex_content.replace('{LINKS}', ' \\\\ ' + r'\small ' + ' $|$ '.join(links))
        else:
            latex_content = latex_content.replace('{LINKS}', '')

        # Остальные секции...
        education = self._generate_education(user_data)
        latex_content = latex_content.replace('{EDUCATION_SECTION}', education)

        experience = self._generate_experience(user_data, keywords)
        latex_content = latex_content.replace('{EXPERIENCE_SECTION}', experience)

        projects = self._generate_projects(user_data, keywords)
        latex_content = latex_content.replace('{PROJECTS_SECTION}', projects)

        skills = self._generate_skills(user_data, keywords)
        latex_content = latex_content.replace('{SKILLS_SECTION}', skills)

        achievements = self._generate_achievements(user_data)
        latex_content = latex_content.replace('{ACHIEVEMENTS_SECTION}', achievements)

        languages = self._generate_languages(user_data)
        latex_content = latex_content.replace('{LANGUAGES_SECTION}', languages)

        interests = self._generate_interests(user_data)
        latex_content = latex_content.replace('{INTERESTS_SECTION}', interests)

        return latex_content

    def generate_pdf(self, user_data, keywords=None):
        """Генерация PDF резюме"""
        latex_content = self.generate_resume(user_data, keywords)

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tex_file = os.path.join(tmpdir, 'resume.tex')
                pdf_file = os.path.join(tmpdir, 'resume.pdf')

                # Записываем LaTeX
                with open(tex_file, 'w', encoding='utf-8') as f:
                    f.write(latex_content)

                # Компилируем в PDF
                try:
                    env = os.environ.copy()
                    env['TEXMFHOME'] = tmpdir
                    env['TEXMFVAR'] = tmpdir
                    env['TEXMFCONFIG'] = tmpdir
                    result = subprocess.run(
                        ['pdflatex', '-interaction=nonstopmode', '-file-line-error', '-output-directory', tmpdir, tex_file],
                        capture_output=True,
                        timeout=240,
                        cwd=tmpdir,
                        env=env
                    )
                    if os.path.exists(pdf_file):
                        with open(pdf_file, 'rb') as f:
                            pdf_data = f.read()
                        if pdf_data:
                            return pdf_data, None
                    if result.returncode != 0:
                        stderr = (result.stderr or b'').decode('utf-8', errors='ignore').strip()
                        stdout = (result.stdout or b'').decode('utf-8', errors='ignore').strip()
                        detail = stderr or stdout
                        if detail:
                            detail = detail[-400:]
                        log_file = os.path.join(tmpdir, 'resume.log')
                        if os.path.exists(log_file):
                            with open(log_file, 'r', encoding='utf-8', errors='ignore') as lf:
                                log_text = lf.read()
                            error_lines = [line.strip() for line in log_text.splitlines() if line.strip().startswith('!')]
                            if error_lines:
                                return None, f"Ошибка компиляции: {error_lines[-1]}"
                        return None, f"Ошибка компиляции: {detail or 'pdflatex exit code'}"

                    return None, "PDF не создался"

                except FileNotFoundError:
                    return None, "pdflatex не установлен"
                except subprocess.TimeoutExpired:
                    return None, "Timeout компиляции"
                except Exception as e:
                    return None, f"Ошибка компиляции: {str(e)}"

        except Exception as e:
            return None, f"Ошибка создания PDF: {str(e)}"

    def _escape_latex(self, text):
        """Экранирование специальных символов LaTeX"""
        if not text:
            return ''
        replacements = {
            '&': r'\&',
            '%': r'\%',
            '$': r'\$',
            '#': r'\#',
            '_': r'\_',
            '{': r'\{',
            '}': r'\}',
            '~': r'\textasciitilde{}',
            '^': r'\^{}'
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    def _generate_education(self, data):
        """Генерация секции образования"""
        if not data.get('university'):
            return ''

        section = r"""\section{Образование}
      \resumeSubHeadingListStart
        \resumeSubheading
          {""" + self._escape_latex(data.get('university', '')) + r"""}{""" + self._escape_latex(
            data.get('study_period', '')) + r"""}
          {""" + self._escape_latex(data.get('degree', '')) + r"""}{}
      \resumeSubHeadingListEnd

    """
        return section

    def _generate_interests(self, data):
        """Генерация секции интересов"""
        interests = data.get('interests', '')
        if not interests:
            return ''

        section = r"""\section{Интересы}
     \begin{itemize}[leftmargin=0.15in, label={}]
        \small{\item{
         """ + self._escape_latex(interests) + r"""
        }}
     \end{itemize}

    """
        return section

    def _generate_projects(self, data, keywords):
        """Генерация секции проектов"""
        projects = data.get('projects', [])
        if not projects:
            return ''

        section = r"""\section{Проекты}
    \resumeSubHeadingListStart
"""

        for proj in projects:
            section += r"""      \resumeProjectHeading
          {\textbf{""" + self._escape_latex(proj.get('project_name', '')) + r"""}}{""" + self._escape_latex(
                proj.get('period', '')) + r"""}
"""
            desc_text = proj.get('project_description', '')
            if desc_text and desc_text.strip():
                section += r"""          \resumeItemListStart
"""
                descriptions = [d.strip() for d in desc_text.split('\n') if d.strip()]

                for desc in descriptions:
                    desc_clean = desc.lstrip('-•').strip()
                    if desc_clean:
                        desc_escaped = self._escape_latex(desc_clean)
                        if keywords:
                            desc_escaped = self._highlight_keywords(desc_escaped, keywords)
                        section += r"""            \resumeItem{""" + desc_escaped + r"""}
"""

                section += r"""          \resumeItemListEnd
"""

        section += r"""    \resumeSubHeadingListEnd

"""
        return section

    def _generate_skills(self, data, keywords):
        """Генерация секции навыков"""
        tech_skills = data.get('technical_skills', '')
        soft_skills = data.get('soft_skills', '')

        if not tech_skills:
            return ''

        section = r"""\section{Навыки}
 \begin{itemize}[leftmargin=0.15in, label={}]
    \small{\item{
"""

        if tech_skills:
            tech_escaped = self._escape_latex(tech_skills)
            if keywords and keywords.get('technical'):
                for kw in keywords['technical']:
                    tech_escaped = tech_escaped.replace(
                        self._escape_latex(kw),
                        r'\textcolor{blue}{' + self._escape_latex(kw) + '}'
                    )
            section += r"""     \textbf{Технические навыки}{: """ + tech_escaped + r"""} \\
"""

        if soft_skills:
            section += r"""     \textbf{Soft skills}{: """ + self._escape_latex(soft_skills) + r"""} \\
"""

        section += r"""    }}
 \end{itemize}

"""
        return section

    def _generate_achievements(self, data):
        """Генерация секции достижений"""
        achievements = data.get('achievements', '')
        if not achievements:
            return ''

        section = r"""\section{Достижения}
 \begin{itemize}[leftmargin=0.15in, label={}]
    \small{\item{
"""

        ach_list = [a.strip() for a in achievements.split('\n') if a.strip()]
        for ach in ach_list:
            ach_clean = ach.lstrip('-•').strip()
            if ach_clean:
                section += r"""     """ + self._escape_latex(ach_clean) + r""" \\
"""

        section += r"""    }}
 \end{itemize}

"""
        return section

    def _generate_languages(self, data):
        """Генерация секции языков"""
        languages = data.get('languages', '')
        if not languages:
            return ''

        section = r"""\section{Языки}
 \begin{itemize}[leftmargin=0.15in, label={}]
    \small{\item{
     """ + self._escape_latex(languages) + r"""
    }}
 \end{itemize}

"""
        return section

    def _highlight_keywords(self, text, keywords):
        """Подсветка ключевых слов"""
        if not keywords:
            return text

        all_keywords = []
        if 'technical' in keywords:
            all_keywords.extend(keywords['technical'])
        if 'keywords' in keywords:
            all_keywords.extend(keywords['keywords'])

        for kw in all_keywords:
            escaped_kw = self._escape_latex(kw)
            if escaped_kw in text:
                text = text.replace(
                    escaped_kw,
                    r'\textcolor{blue}{' + escaped_kw + '}',
                    1
                )

        return text

    def _generate_experience(self, data, keywords):
        """Генерация секции опыта работы"""
        experiences = data.get('experiences', [])
        if not experiences:
            return ''

        section = r"""\section{Опыт работы}
  \resumeSubHeadingListStart
"""

        for exp in experiences:
            section += r"""    \resumeSubheading
      {""" + self._escape_latex(exp.get('position', '')) + r"""}{""" + self._escape_latex(
                exp.get('work_period', '')) + r"""}
      {""" + self._escape_latex(exp.get('company', '')) + r"""}{}
      \resumeItemListStart
"""
            # Разбиваем responsibilities на пункты
            resp_text = exp.get('responsibilities', '')
            responsibilities = [r.strip() for r in resp_text.split('\n') if r.strip()]

            for resp in responsibilities:
                resp_clean = resp.lstrip('-•').strip()
                if not resp_clean:
                    continue
                resp_escaped = self._escape_latex(resp_clean)
                # Подсвечиваем ключевые слова
                if keywords:
                    resp_escaped = self._highlight_keywords(resp_escaped, keywords)
                section += r"""        \resumeItem{""" + resp_escaped + r"""}
"""

            section += r"""      \resumeItemListEnd
"""

        section += r"""  \resumeSubHeadingListEnd

"""
        return section
