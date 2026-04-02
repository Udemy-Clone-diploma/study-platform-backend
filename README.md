# Study Platform — Backend

REST API для навчальної платформи, побудований на Django та Django REST Framework.

## Технології

- [Python 3.11+](https://www.python.org/)
- [Django 6](https://www.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [python-decouple](https://github.com/HBNetwork/python-decouple) — конфігурація через `.env`
- SQLite (розробка)

## Вимоги

- Python 3.11+
- pip

## Встановлення

### 1. Клонування репозиторію

```bash
git clone https://github.com/YOUR_ORG/study-platform-backend.git
cd study-platform-backend
```

### 2. Створення та активація віртуального середовища

```bash
python -m venv venv
```

**Windows:**
```bash
venv\Scripts\activate
```

**macOS / Linux:**
```bash
source venv/bin/activate
```

### 3. Встановлення залежностей

```bash
pip install -r requirements.txt
```

### 4. Налаштування змінних середовища

```bash
cp .env.example .env
```

Відкрийте `.env` і заповніть значення (SECRET_KEY та DEBUG обов'язкові).

### 5. Застосування міграцій

```bash
python manage.py migrate
```

### 6. Запуск сервера

```bash
python manage.py runserver
```

API доступне за адресою: `http://127.0.0.1:8000`  
Адмін-панель: `http://127.0.0.1:8000/admin`

## Команди

```bash
python manage.py createsuperuser       # Створити адміністратора
python manage.py makemigrations        # Створити міграції після змін у моделях
python manage.py migrate               # Застосувати міграції
python manage.py test <назва_застосунку>  # Запустити тести конкретного застосунку
```

## Структура проєкту

```
.
├── config/           # Налаштування Django (settings, urls, wsgi, asgi)
├── manage.py
├── requirements.txt
└── .env.example
```

> Нові Django-застосунки додаються поряд із `config/` і реєструються в `INSTALLED_APPS`.
