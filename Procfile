web: gunicorn tripplanner.wsgi --log-file -
web: python manage.py migrate && gunicorn tripplanner.wsgi