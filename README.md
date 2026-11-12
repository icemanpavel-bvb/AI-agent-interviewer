# AI-агент интервьюер (TEAM-12)

Диалоговый AI-ассистент для первичного текстового интервью кандидата по вакансии.
Ассистент задаёт вопросы рекрутера, уточняет неполные ответы (до 2 уточнений на вопрос) и готовит протокол с цитатами **без баллов**.
Решение «пригласить на 2-й этап / отклонить / отложить» принимает рекрутер.

- Архитектура и описание работы: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- Журнал решений и открытые вопросы: [`docs/decisions.md`](docs/decisions.md)
- Карта файлов с описанием: [`docs/STRUCTURE.md`](docs/STRUCTURE.md)
- План реализации: [`docs/NEXT_STEPS.md`](docs/NEXT_STEPS.md)
- Схемы: [`docs/diagrams/`](docs/diagrams) (исходники `.mmd`, готовые `.svg`/`.png`)

## Структура проекта

```
AI-agent-interviewer/
├── docs/
│   ├── ARCHITECTURE.md          # архитектура, решения, API, eval, план
│   └── diagrams/                # 01 компоненты · 02 автомат диалога · 03 статусы
│                                # 04 последовательность хода · 05 отчёт · 06 ER
├── backend/                     # Python 3.11 · FastAPI · модульный монолит
│   ├── app/
│   │   ├── main.py              # точка входа
│   │   ├── core/                # настройки, безопасность (JWT, токены ссылок), логи без ПДн
│   │   ├── db/                  # подключение к PostgreSQL
│   │   ├── models/              # ORM: vacancy, question, candidate, application, session, message, report…
│   │   ├── schemas/             # Pydantic: API и схема протокола (report.py)
│   │   ├── api/v1/              # auth, vacancies, applications, reports, interview (чат кандидата)
│   │   ├── services/            # контур рекрутера: сценарии, ссылки, статусы и решения
│   │   ├── interview/           # ★ Interview Engine: engine, policy, analyzer, followup, guardrails, prompts/
│   │   ├── llm/                 # LLM Gateway: Ollama (по умолч.), GigaChat, маскирование ПДн
│   │   ├── reporting/           # протокол: builder, validators (цитаты, без оценок), PDF, prompts/
│   │   ├── notifications/       # email / Telegram
│   │   └── jobs/                # Scheduler: «Отложенные», истечение ссылок, retention
│   ├── migrations/              # Alembic
│   └── tests/                   # unit (policy, статусы, валидаторы) + integration
├── frontend/                    # React + TS + Vite
│   └── src/
│       ├── candidate/           # согласие + чат по ссылке /i/:token
│       └── recruiter/           # вакансии, редактор сценария, кандидаты, отчёт и решение
├── scenarios/                   # сценарии: ОМТО, ML Junior, ML Middle, студент
├── eval/                        # синтетические диалоги и метрики качества
├── docker-compose.yml           # db · backend · frontend (Ollama — в системе)
└── .env.example
```

## Быстрый старт (когда код будет реализован)

```bash
cp .env.example .env
docker compose up -d --build
# модель — один раз, Ollama работает в системе (см. docs/decisions.md, D-001)
ollama pull hf.co/ai-sage/GigaChat3.1-10B-A1.8B-GGUF:Q4_K_M
ollama cp hf.co/ai-sage/GigaChat3.1-10B-A1.8B-GGUF:Q4_K_M gigachat-lightning
docker compose exec backend alembic upgrade head
# кабинет рекрутера: http://localhost:8080/app
```

## Разработка

```bash
pip install -e "backend[dev]" pre-commit
pre-commit install                      # проверки перед каждым коммитом
python scripts/validate_scenarios.py    # проверка сценариев
cd backend && pytest                    # тесты
ruff check backend scripts eval && ruff format backend scripts eval
```

Правила работы с репозиторием:
- в `main` — только через Pull Request с одним ревьюером и зелёным CI (`.github/workflows/ci.yml`);
- ветки задач: `feat/...`, `fix/...`, `docs/...`;
- `.env`, лекции и гайд T06 в репозиторий не попадают (`.gitignore`, D-007).
