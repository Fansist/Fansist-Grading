# Container for the Fansist Grading QR report web service (web_report / wsgi).
#
#   docker build -t fansist-grading .
#   docker run -p 8000:8000 -v $PWD/cards:/data/cards \
#       -e FANSIST_STORE=/data/cards -e FANSIST_BASE_URL=https://grade.example \
#       fansist-grading
#
# Grade cards into the mounted store (host side or another container):
#   python report.py card.jpg --store ./cards --base-url https://grade.example
FROM python:3.11-slim

# OpenCV (headless) needs libGL + glib at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-deploy.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-deploy.txt

COPY *.py ./

ENV FANSIST_STORE=/data/cards
VOLUME ["/data/cards"]
EXPOSE 8000

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "wsgi:app"]
