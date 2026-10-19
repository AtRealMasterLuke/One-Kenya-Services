FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# GeoDjango needs GEOS, PROJ and GDAL at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends binutils libproj-dev gdal-bin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
ARG DEV=0
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ "$DEV" = "1" ]; then pip install --no-cache-dir -r requirements-dev.txt; fi

COPY . .
RUN DJANGO_SECRET_KEY=collectstatic-only python manage.py collectstatic --noinput

RUN useradd --create-home app && chown -R app /app
USER app

EXPOSE 8000
CMD ["sh", "bin/start.sh"]
