Telegram Invoice Bot

Telegram-бот для обработки PDF-инвойсов с использованием локального парсинга и OpenAI.

Возможности

📄 обработка PDF-инвойсов;

🔎 извлечение данных из инвойса;

🤖 анализ данных с помощью OpenAI;

🔄 сверка результатов локального парсера и GPT;

✏️ ручное исправление данных инвойса;

🎲 случайные факты о платежах и банковских технологиях;

💬 диалог с ChatGPT;

🧠 интерактивный квиз с подсчётом результата.

Технологии

Python

aiogram

OpenAI API

pypdf

python-dotenv

Структура проекта

Telegram-invoice-bot/
├── assets/
│   ├── img.png
│   └── random_invoice_fact.png
├── keyboards/
│   ├── main_menu.py
│   ├── quiz.py
│   └── random_fact.py
├── config.py
├── handlers.py
├── invoice_ai.py
├── invoice_parser.py
├── invoice_reconciliation.py
├── main.py
├── openai_client.py
├── requirements.txt
└── README.md

Установка

Создать виртуальное окружение:

python -m venv .venv

Активировать виртуальное окружение:

macOS / Linux

source .venv/bin/activate

Установить зависимости:

pip install -r requirements.txt

Переменные окружения

Создать файл .env в корне проекта:

TELEGRAM_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key

Файл .env не должен добавляться в Git.

Запуск

Запустить бота:

python main.py

После запуска бот начинает получать сообщения через Telegram polling.

Команды

/start — открыть главное меню;

/help — список доступных команд;

/random — получить случайный факт;

/gpt — начать диалог с ChatGPT;

/quiz — начать квиз.

Основные функции также доступны через кнопки главного меню.

Логирование

В проекте используется стандартное логирование Python для отслеживания запуска бота, обработки запросов и возможных ошибок.

Безопасность

Секретные ключи хранятся в переменных окружения и не должны публиковаться в репозитории.

Файл .env, виртуальное окружение и временные файлы добавлены в .gitignore.

Дополнительные технологии

В проекте используются:

OpenAI Responses API для работы с GPT;

pypdf для извлечения текста из PDF;

aiogram для работы с Telegram Bot API;

inline- и reply-клавиатуры Telegram для взаимодействия с пользователем.
