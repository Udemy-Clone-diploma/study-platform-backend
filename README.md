# Study Platform — Backend

REST API для навчальної платформи, побудований на Django та Django REST Framework.

## Технології

- [Python 3.13](https://www.python.org/)
- [Django 6](https://www.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [python-decouple](https://github.com/HBNetwork/python-decouple) — конфігурація через `.env`
- [PostgreSQL 17](https://www.postgresql.org/)
- [psycopg2-binary](https://pypi.org/project/psycopg2-binary/) — драйвер PostgreSQL

## Вимоги

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [VS Code](https://code.visualstudio.com/) з розширенням [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

## Запуск

### 1. Клонування репозиторію

```bash
git clone https://github.com/YOUR_ORG/study-platform-backend.git
cd study-platform-backend
```

### 2. Налаштування змінних середовища

```bash
cp .env.example .env
```

Заповни `.env` — мінімум `SECRET_KEY` і `DB_PASSWORD`.

### 3. Відкрити в DevContainer

У VS Code: `Ctrl+Shift+P` → **Dev Containers: Reopen in Container**

Docker автоматично підніме два контейнери: `app` (Python) і `db` (PostgreSQL 17).

### 4. Застосувати міграції та запустити сервер

```bash
python manage.py migrate
python manage.py runserver
```

API: `http://localhost:8000`  
Адмін-панель: `http://localhost:8000/admin`

## Команди

```bash
python manage.py createsuperuser          # Створити адміністратора
python manage.py makemigrations           # Створити міграції після змін у моделях
python manage.py migrate                  # Застосувати міграції
python manage.py test <назва_застосунку>  # Запустити тести
```

## Структура проєкту

```
.
├── .devcontainer/
│   ├── devcontainer.json   # Конфігурація VS Code DevContainer
│   └── docker-compose.yml  # Сервіси: app + db
├── apps/
│   └── users/              # Автентифікація, профілі користувачів
├── config/                 # Налаштування Django (settings, urls, wsgi, asgi)
├── manage.py
├── requirements.txt
└── .env.example            # Шаблон змінних середовища
```

> Нові Django-застосунки додаються в `apps/` і реєструються в `INSTALLED_APPS`.
