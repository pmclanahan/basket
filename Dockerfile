FROM debian:jessie

RUN adduser --uid 1000 --disabled-password --gecos '' --no-create-home webdev
WORKDIR /app

EXPOSE 8000
CMD ["bin/run-prod.sh"]

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential python2.7 libpython2.7 python-dev \
        python-pip gettext python-mysqldb netcat

# Get pip 8
COPY bin/pipstrap.py bin/pipstrap.py
RUN bin/pipstrap.py

# Install app
COPY requirements /app/requirements
RUN pip install --require-hashes --no-cache-dir -r requirements/prod.txt

COPY . /app
RUN DEBUG=False SECRET_KEY=foo ALLOWED_HOSTS=localhost, DATABASE_URL=sqlite:// SUPERTOKEN=bar \
    ./manage.py collectstatic --noinput

# Change User
RUN chown webdev.webdev -R .
USER webdev
