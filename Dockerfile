# SETU ML service — the Hugging Face Space image (Part 22).
#
# This builds `services/ml` ONLY. It is deliberately not an image for
# `services/api`: Part 22's whole point is that the two have different failure
# domains. Render's free tier is ~512 MB, and torch's import footprint alone is
# 300-500 MB before either model is loaded — an all-in-one image OOM-kills on
# the first real inference and, because the health check only sees a process
# restart, that masquerades as "flaky cold starts" for days.
#
# The Space repo IS this repo. That is a deliberate choice over a separate
# self-contained Space folder: `services/ml/server.py` imports
# `services.api.settings`, so a standalone Space would need a vendored copy of
# it, and a second copy of the translate/embed endpoints is exactly how the
# Space and the API drift into disagreeing about which model is loaded. One
# source of truth, one Dockerfile, `.dockerignore` keeps the image small.

FROM python:3.12-slim

# HF Spaces runs as a non-root user with UID 1000 and expects the app on 7860.
# HOME must be writable or huggingface_hub cannot cache the model weights, which
# fails at *runtime* on first inference rather than at build time.
RUN useradd -m -u 1000 setu
ENV HOME=/home/setu \
    HF_HOME=/home/setu/.cache/huggingface \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860

WORKDIR /app

# ML deps only — NOT requirements.txt. The API's 169 pinned packages include
# asyncpg, twilio, firebase-admin and PostGIS tooling that this service has no
# use for, and installing them here would both bloat the image and blur the
# isolation that check_no_torch.py exists to enforce in the other direction.
COPY --chown=setu:setu services/ml/requirements-ml.txt /app/requirements-ml.txt
# torch first, in its own layer. IndicTransToolkit declares cython and builds
# against torch, and installing it in the same resolution pass has historically
# failed when pip picks its build order badly. Separate layers also mean a
# failure names which package broke instead of one opaque resolver error — and
# the ~2 GB torch layer is cached across rebuilds, which matters a lot on a free
# Space where every push otherwise re-downloads it.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir "torch>=2.2,<3" \
 && pip install --no-cache-dir -r /app/requirements-ml.txt

# Exactly what server.py's import graph needs, and nothing else. Verified from
# the AST rather than assumed: server.py imports importlib, typing, fastapi,
# pydantic, services.api.settings and services.ml.flores. All three
# __init__.py files are empty, so no sibling module is pulled in
# transitively. flores.py has no torch / asyncpg / httpx import — it is safe
# in this image.
#
# Notably this does NOT copy the rest of services/ml/. translate.py, dedup.py,
# reach_risk.py and client.py all import asyncpg or httpx, which this image
# deliberately does not install — shipping them would put modules in the image
# that crash the moment anything imports them. The Space serves /translate and
# /embed; it does not talk to Postgres. The API owns the database, and the
# translation cache it writes lives there (Part 22 point 5: the demo reads the
# cache and never calls the Space live).
COPY --chown=setu:setu services/__init__.py       /app/services/__init__.py
COPY --chown=setu:setu services/api/__init__.py   /app/services/api/__init__.py
COPY --chown=setu:setu services/api/settings.py   /app/services/api/settings.py
COPY --chown=setu:setu services/ml/__init__.py    /app/services/ml/__init__.py
COPY --chown=setu:setu services/ml/flores.py      /app/services/ml/flores.py
COPY --chown=setu:setu services/ml/server.py      /app/services/ml/server.py

USER setu

# Models load once at startup, not per request (Part 22 point 4). Single worker
# on purpose: two workers would each load their own ~1.7 GB of weights.
EXPOSE 7860
CMD ["uvicorn", "services.ml.server:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
