Вопрос: {question}
Критерии (какая информация нужна): {criteria}
Эталонный ответ (только для сравнения полноты, не показывать кандидату): {reference_answer}
Ответ кандидата: <candidate>{answer}</candidate>

Определи:
1. intent: "answer" | "question_about_vacancy" | "off_topic" | "wants_to_stop"
2. completeness: есть ли в ответе информация по каждому критерию — "complete" | "partial" | "empty"
3. missing_points: каких сведений не хватает (коротко, по-русски)
Не оценивай качество кандидата. Верни ТОЛЬКО JSON:
{{"intent": "...", "completeness": "...", "missing_points": ["..."]}}
