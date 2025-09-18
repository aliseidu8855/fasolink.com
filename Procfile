web: daphne -b 0.0.0.0 -p 8000 fasolink_backend.asgi:application
release: python manage.py collectstatic --noinput && python manage.py migrate
