QUESTION_GENERATION_PROMPT = """[TASK:EXAM_GEN]
Ты — ассистент по подготовке к экзамену. Используя приведённые ниже экзаменационные
материалы курса, подготовь {question_count} письменных вопросов для студента на языке «{language}».
Вопросы должны соответствовать темам материалов, по одному вопросу на элемент списка.

Верни только JSON-массив:
[{{"question": "текст вопроса", "reference_answer": "краткий эталонный ответ или критерии оценки"}}]"""

ANSWER_EVALUATION_PROMPT = """[TASK:EXAM_EVAL]
Ты — экзаменатор. Оцени письменный ответ студента на вопрос, опираясь на эталонный ответ
(если он задан) и материалы курса. Отвечай на языке «{language}».

Верни только JSON-объект:
{{
  "verdict": "correct" | "partial" | "incorrect",
  "score": целое число от 0 до 100,
  "summary": "краткая оценка одной фразой",
  "issues": ["конкретные недочёты ответа"],
  "recommendation": "практический совет, как улучшить ответ"
}}
Критерии: correct — ответ полный и верный (score ≥ 75); partial — верен частично (35–74);
incorrect — неверен или отсутствует (< 35).

<course_context>
{context}
</course_context>

<question>
{question}
</question>

<reference_answer>
{reference_answer}
</reference_answer>

<answer>
{student_answer}
</answer>"""
