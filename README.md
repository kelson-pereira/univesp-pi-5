# univesp-pi-5

## UNIVESP, 2026

Projeto Integrador em Computação V - Grupo 22

### Comandos de instalação do python3:

`brew upgrade && brew update && brew install python3 && brew cleanup phyton3 && python3 --version`

### Comandos de instalação do django e demais componentes:

`pip3 install --upgrade pip`

`pip3 install --upgrade Django`

`pip3 install --upgrade whitenoise`

`pip3 install --upgrade dj-database-url`

`pip3 install --upgrade django-heroku`

`pip3 install --upgrade gunicorn`

### Comandos de inicialização do projeto:

`pip3 freeze`

`django-admin startproject univesp_pi_5`

`mv univesp_pi_5 univesp-pi-5 && cd univesp-pi-5`

`django-admin startapp voltguard`

### Comandos para execução do projeto localmente:

`cd univesp-pi-5`

`python3 manage.py makemigrations`

`python3 manage.py migrate`

`python3 manage.py collectstatic --noinput --clear`

`python3 manage.py runserver 0.0.0.0:8000`

### Comandos para recriar o banco:

`cd univesp-pi-5`

`find . -path "*/migrations/*.py" -not -name "__init__.py" -delete`

`find . -path "*/migrations/*.pyc" -delete`

`find . -path "*/db.sqlite3" -delete`

`python3 manage.py makemigrations`

`python3 manage.py migrate`

### Comandos para criar banco de dados na plataforma Heroku:

`heroku login`

`heroku run python manage.py makemigrations --app voltguard`

`heroku run python manage.py migrate --app voltguard`

### Comandos de debug na Heroku:

`heroku logs --tail --app voltguard`

`heroku pg:psql --app voltguard`

`SELECT * FROM voltguard_sensor WHERE voltguard_sensor.device_id = 'XX:XX:XX:XX:XX:XX' and voltguard_sensor.sensor_type_id = 'vltA';`
