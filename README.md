# AI-агент интервьюер (TEAM-12)

Диалоговый AI-ассистент для **первичного текстового интервью** кандидата по вакансии.
Ассистент задаёт вопросы из сценария вакансии, уточняет неполные ответы (не больше 2 уточнений на вопрос)
и готовит **протокол с дословными цитатами и без баллов**. Решение «пригласить на 2-й этап / отклонить / отложить»
всегда принимает рекрутер.

Тот же движок умеет **проверку знаний** по учебному курсу — например, подготовку к экзамену по лекциям.

## Статус

| Что | Состояние |
|---|---|
| Веб-демо в браузере: выбор сценария, чат, отладка, протокол | ✅ работает (сессии в памяти сервера) |
| Интервью в терминале с локальной моделью (GigaChat 3.1 Lightning через Ollama) | ✅ работает |
| 4 сценария: аналитик ОМТО, ML-инженер Junior и Middle, подготовка к экзамену по NLP | ✅ ОМТО и Junior готовы, Middle и NLP — черновики |
| Анализ ответа по пунктам с проверкой цитат, уточнения, протокол | ✅ работает, покрыто тестами |
| Полная веб-версия: БД, приглашения, кабинет рекрутера, PDF | 🧩 спроектировано, в разработке |

Подробно, какой файл готов, а какой пока заготовка, — в [руководстве разработчика](docs/DEVELOPER_GUIDE.md#2-что-уже-работает-а-что-заготовка).

## Быстрый старт

Нужно: **Python 3.11+, Node.js 18+ (для веб-версии), 16 ГБ RAM, ~8 ГБ на диске.** Видеокарта не нужна.

Ниже — команды для **Linux и macOS**. На **Windows** — [отдельный раздел](#быстрый-старт-на-windows).

### 1. Код и окружение

```bash
git clone git@github.com:icemanpavel-bvb/AI-agent-interviewer.git
cd AI-agent-interviewer
python3 -m venv .venv
source .venv/bin/activate
pip install -e "backend[dev]"
```

### 2. Модель (один раз)

```bash
curl -fsSL https://ollama.com/install.sh | sh          # установить Ollama
ollama pull hf.co/ai-sage/GigaChat3.1-10B-A1.8B-GGUF:Q4_K_M   # 6,5 ГБ
ollama cp hf.co/ai-sage/GigaChat3.1-10B-A1.8B-GGUF:Q4_K_M gigachat-lightning
```

Желательно, чтобы модель не выгружалась из памяти между ходами (иначе каждый ответ ~30 с вместо ~3 с):

```bash
sudo systemctl edit ollama
# вставить и сохранить:
# [Service]
# Environment="OLLAMA_KEEP_ALIVE=30m"
# Environment="OLLAMA_NUM_PARALLEL=1"
sudo systemctl restart ollama
```

Почему именно эта модель и такие настройки — [`docs/decisions.md`](docs/decisions.md), D-001.

### 3. Запуск в браузере (удобнее для тестов)

Два терминала, оба из корня репозитория.

**Терминал 1 — бэкенд:**
```bash
source .venv/bin/activate
cd backend
DEMO_MODE=true uvicorn app.main:app --reload
```

**Терминал 2 — интерфейс** (Node.js: `sudo apt install nodejs npm`, если ещё нет):
```bash
cd frontend
npm install        # один раз
npm run dev
```

Открыть **http://localhost:5173/demo** — выбрать сценарий и начать. Кнопка **«Отладка»** в чате показывает,
какие пункты модель нашла в последнем ответе, с цитатами и временем вызова. В конце — протокол и кнопка «Скачать JSON».

Демо-сессии хранятся в памяти сервера: перезапуск бэкенда их стирает. Вместо `DEMO_MODE=true` в команде можно
скопировать `.env.example` в `.env` — там демо-режим уже включён.

### 4. Запуск в терминале

```bash
cd backend
python -m app.cli --list                          # сценарии и темы
python -m app.cli ml_junior                       # собеседование Junior ML-инженера
python -m app.cli student_course                  # 10 случайных вопросов по NLP
python -m app.cli student_course --topic T03      # все вопросы одной темы (Word2Vec)
python -m app.cli omto_analyst --verbose          # + время каждого вызова модели
```

Первый ответ после запуска может идти до 30 секунд — модель загружается. Дальше ~3–6 секунд на ход.
Выйти досрочно — **Ctrl+C** (протокол всё равно будет). В конце печатается протокол: критерии или темы, пункты
с цитатами, а для проверки знаний — эталонные ответы для повторения. Полный протокол сохраняется
в `storage/cli_sessions/` (эта папка не попадает в git).

Если что-то не запускается — [частые проблемы](docs/DEVELOPER_GUIDE.md#8-частые-проблемы).

## Быстрый старт на Windows

Все команды — в **PowerShell** (лучше в Windows Terminal: Пуск → «Терминал»). Шаги составлены по устройству кода;
на настоящей Windows их ещё никто из команды не проходил — если что-то отличается, поправьте этот раздел.

### 0. Программы (один раз)

Проще всего через `winget` (встроен в Windows 10/11):

```powershell
winget install Git.Git Python.Python.3.13 OpenJS.NodeJS.LTS Ollama.Ollama
```

Или вручную с сайтов: [git-scm.com](https://git-scm.com), [python.org](https://www.python.org/downloads/)
(при установке отметить **Add python.exe to PATH**), [nodejs.org](https://nodejs.org) (LTS), [ollama.com](https://ollama.com/download).

**После установки закройте и заново откройте PowerShell**, иначе новые команды не найдутся.
Проверка: `git --version`, `py --version` (нужен 3.11+), `node -v` (18+), `ollama --version`.

### 1. Код и окружение

```powershell
cd ~\Documents
git clone https://github.com/icemanpavel-bvb/AI-agent-interviewer.git
cd AI-agent-interviewer
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e "backend[dev]"
Copy-Item .env.example .env
```

- Репозиторий приватный: при `git clone` откроется окно входа в GitHub — войдите аккаунтом, которого пригласили в репозиторий.
- Если `Activate.ps1` пишет, что **выполнение сценариев отключено**, один раз выполните
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (ответить `Y`) и повторите.
- После активации в начале строки появляется `(.venv)`. Без этого `pip` и `uvicorn` возьмутся не из проекта.
- Если `pip install -e "backend[dev]"` падает на сборке какого-то пакета, поставьте только нужное для демо:
  `pip install pydantic pydantic-settings fastapi "uvicorn[standard]" httpx pytest`.
- Файл `.env` включает демо-режим (`DEMO_MODE=true`) — на Windows так проще, чем переменные в командной строке.

### 2. Модель (один раз)

Ollama после установки работает в фоне (значок в трее).

```powershell
ollama pull hf.co/ai-sage/GigaChat3.1-10B-A1.8B-GGUF:Q4_K_M
ollama cp hf.co/ai-sage/GigaChat3.1-10B-A1.8B-GGUF:Q4_K_M gigachat-lightning
ollama list
```

Чтобы модель не выгружалась между ходами (иначе каждый ответ ~30 с):

```powershell
setx OLLAMA_KEEP_ALIVE 30m
setx OLLAMA_NUM_PARALLEL 1
```

Затем **перезапустите Ollama**: правый клик по значку в трее → Quit, потом запустить Ollama из меню Пуск.

Если в ноутбуке есть видеокарта NVIDIA — Ollama задействует её сама, ответы будут быстрее, чем на процессоре.

### 3. Запуск в браузере

**Окно PowerShell 1 — бэкенд:**
```powershell
cd ~\Documents\AI-agent-interviewer
.venv\Scripts\Activate.ps1
cd backend
uvicorn app.main:app --reload
```
Должно появиться `Uvicorn running on http://127.0.0.1:8000` без ошибок под ним.

**Окно PowerShell 2 — интерфейс:**
```powershell
cd ~\Documents\AI-agent-interviewer\frontend
npm install
npm run dev
```
Если `npm` пишет про **отключённое выполнение сценариев** — та же команда `Set-ExecutionPolicy` из шага 1 (или запускайте `npm.cmd` вместо `npm`).

Открыть **http://localhost:5173/demo**.

### 4. Запуск в терминале

```powershell
cd ~\Documents\AI-agent-interviewer
.venv\Scripts\Activate.ps1
cd backend
python -m app.cli --list
python -m app.cli student_course --verbose
```

### Если что-то не так на Windows

| Симптом | Что сделать |
|---|---|
| `py` или `python` открывает Microsoft Store | Параметры → Приложения → Дополнительные параметры → Псевдонимы выполнения приложений → выключить `python.exe` и `python3.exe`; переоткрыть PowerShell |
| `uvicorn` / `pip` не найдены | Не активировано окружение: `.venv\Scripts\Activate.ps1` из корня репозитория |
| `ollama` не найдена | Переоткрыть PowerShell после установки; проверить, что Ollama запущена (значок в трее) |
| В чате «Модель недоступна» | `ollama list` — есть ли `gigachat-lightning`; в `.env` должно быть `OLLAMA_URL=http://localhost:11434` |
| Мало памяти (8 ГБ), всё тормозит | Модель занимает ~6,5 ГБ. Закрыть браузерные вкладки и лишние программы или взять модель поменьше: `ollama pull qwen3.5:4b` (имя проверить на [ollama.com/library](https://ollama.com/library)) и в `.env` указать `LLM_MODEL=qwen3.5:4b` |
| `git` предупреждает про LF/CRLF | Ничего делать не нужно: файл `.gitattributes` держит единые переводы строк |

Альтернатива — **WSL2** (Linux внутри Windows, `wsl --install`): в нём работают Linux-команды из раздела выше
без изменений, а Ollama можно оставить в самой Windows — из WSL она доступна по `localhost:11434`.

## Облачные модели — быстрее локальной (по желанию)

Локальная GigaChat Lightning на процессоре проверяет длинный ответ 40–120 с. Облачные модели
по бесплатным ключам отвечают за секунды. Модель выбирается на странице `/demo` в списке
«Модель для проверки ответов»; сессия до конца идёт на выбранной модели (D-013).

1. Получите бесплатный ключ у одного или нескольких сервисов: [Groq](https://console.groq.com/keys),
   [OpenRouter](https://openrouter.ai/settings/keys) (модели с `:free` в имени),
   [GigaChat API](https://developers.sber.ru/studio) (ключ авторизации, тариф для физлиц).
2. Скопируйте образец и впишите ключи:
   ```bash
   cp llm_keys.example.json llm_keys.json          # Windows: copy llm_keys.example.json llm_keys.json
   ```
   Формат — словарь «имя модели → ключ»; имя пишется как `сервис/модель у сервиса`:
   ```json
   {
     "groq/llama-3.3-70b-versatile": "gsk_...",
     "openrouter/openai/gpt-oss-120b:free": "sk-or-..."
   }
   ```
   Поддерживаемые сервисы: `groq`, `openrouter`, `gigachat`, `gemini`, `mistral`, `cerebras`,
   `github`, `openai`; любой другой OpenAI-совместимый — полной записью с `base_url`
   (пример в `llm_keys.example.json`). Записи с незаполненным ключом пропускаются.
3. Перезапускать сервер не нужно: файл перечитывается при изменении. Обновите страницу `/demo`.

**Важно:**
- `llm_keys.json` в `.gitignore` — **не коммитьте ключи**, репозиторий публичный. Если ключ
  всё же попал в git — сразу отзовите его в кабинете сервиса.
- Ответы уходят во внешний сервис. Для учёбы и тестов это нормально; **не вводите личные данные**.
  У Gemini и Mistral бесплатный тариф может использовать запросы для обучения. Для настоящих
  кандидатов — только локальная модель или сервис с договором (152-ФЗ).
- Лимиты бесплатных тарифов меняются; при превышении ход не засчитывается, ответ можно отправить
  ещё раз или выбрать другую модель.

| Сообщение | Что делать |
|---|---|
| ключ не принят (HTTP 401) | проверьте ключ в `llm_keys.json` |
| HTTP 403 | ключ без прав или сервис недоступен из вашего региона — попробуйте OpenRouter или GigaChat |
| лимит бесплатного тарифа (HTTP 429) | подождите минуту или выберите другую модель |
| модель не найдена (HTTP 404) | имя модели у сервиса изменилось — посмотрите список на сайте сервиса |
| GigaChat: ошибка сертификата | скачайте корневой сертификат «Russian Trusted Root CA» и укажите путь к нему в `"ca_file"` |

## Как это работает (коротко)

1. Сценарий вакансии (`scenarios/*.json`) задаёт вопросы, критерии и **пункты проверки** — что должно прозвучать в хорошем ответе.
2. На каждый ответ модель говорит по каждому пункту: раскрыт / частично / нет — и приводит цитату.
3. **Код** проверяет, что цитата действительно есть в ответе, считает полноту и решает: уточнить или идти дальше. Лимиты и порядок вопросов задаёт код, а не модель.
4. В конце — протокол по критериям с цитатами. Критерии, которые подтверждаются только практикой (например, качество кода), всегда помечены «нужна практическая проверка».

Схемы и полное описание — [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Документация

| Документ | Когда читать |
|---|---|
| [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md) | **Начать здесь, если пишете код:** как устроен код, что за что отвечает, рецепты, тесты, git |
| [`scenarios/README.md`](scenarios/README.md) | Формат сценария, как добавить вакансию |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Архитектура всей системы (включая веб-версию): компоненты, статусы, данные, API, безопасность |
| [`docs/decisions.md`](docs/decisions.md) | Что решили и почему (выбор модели, хранение, проверка по пунктам) + открытые вопросы |
| [`docs/STRUCTURE.md`](docs/STRUCTURE.md) | Карта всех файлов, включая будущие |
| [`docs/NEXT_STEPS.md`](docs/NEXT_STEPS.md) | План по этапам с чек-листами |
| [`docs/diagrams/`](docs/diagrams) | Схемы: исходники `.mmd`, готовые `.svg` / `.png` |

## Структура репозитория

```
AI-agent-interviewer/
├── scenarios/            ✅ сценарии вакансий и курса (JSON)
├── backend/
│   ├── app/
│   │   ├── api/v1/       ✅ demo.py, interview.py — API демо и чата · 🧩 остальное
│   │   ├── cli/          ✅ консольный прототип: python -m app.cli
│   │   ├── interview/    ✅ диалог: runner, анализ ответа, уточнения, политика, защита, промпты
│   │   ├── llm/          ✅ работа с моделью: Ollama, фейковая модель для тестов, промпты
│   │   ├── reporting/    ✅ протокол и проверки кодом (цитаты, без оценок) · 🧩 PDF
│   │   ├── schemas/      ✅ схема сценария · 🧩 схемы API
│   │   ├── services/     ✅ статусы кандидата · 🧩 остальное
│   │   ├── db/ models/ notifications/ jobs/   🧩 полная веб-версия
│   │   └── core/         🧩 настройки, безопасность
│   ├── tests/unit/       ✅ тесты (модель не нужна)
│   └── migrations/       🧩 миграции БД
├── frontend/             ✅ /demo и чат с протоколом (React) · 🧩 кабинет рекрутера
├── eval/                 🧩 оценка качества
├── scripts/              ✅ validate_scenarios.py
└── docs/                 документация
```
✅ — работает · 🧩 — заготовка с описанием, кода пока нет

## Разработка

```bash
source .venv/bin/activate
pip install pre-commit && pre-commit install    # проверки перед каждым коммитом
cd backend && pytest                            # тесты, ~1 с
cd frontend && npm run build                    # проверка типов и сборка интерфейса
python scripts/validate_scenarios.py            # из корня: проверка сценариев
ruff check backend scripts eval && ruff format backend scripts eval
```

- В `main` — только через Pull Request с зелёным CI.
- Ветки: `feat/...`, `fix/...`, `docs/...`.
- Не коммитим: `.env`, `лекции/`, гайд `T06_*.docx`, `storage/` — всё уже в `.gitignore`.

Подробно — [руководство разработчика](docs/DEVELOPER_GUIDE.md#7-работа-с-git).

## Команда

| Участник | Зона |
|---|---|
| Кондратов Д. С. | Interview Engine, работа с моделью, промпты, сценарии |
| Бойченко П. С. | Backend: БД, API, статусы, авторизация, Docker |
| Щербакова В. Н. | Frontend: чат кандидата и кабинет рекрутера |
| Мальцева А. Е. | Протокол и PDF, оценка качества, уведомления |

Распределение — предложение из [`ARCHITECTURE.md`](docs/ARCHITECTURE.md), §13; уточняйте в команде.
