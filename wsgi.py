"""wsgi.py

Production entry point for the QR report web service. Serve with gunicorn:

    FANSIST_STORE=/data/cards gunicorn -w 2 -b 0.0.0.0:8000 wsgi:app

``FANSIST_STORE`` is the directory of graded-card folders (written by
``report.save_report`` / the grading machine). See the Dockerfile.
"""

from __future__ import annotations

import os

from web_report import create_app

app = create_app(os.environ.get("FANSIST_STORE", "./cards"))
