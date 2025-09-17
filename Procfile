web: gunicorn fasolink_backend.wsgi
release: python manage.py collectstatic --noinput && python manage.py migrate
