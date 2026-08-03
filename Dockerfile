# syntax=docker/dockerfile:1.20

ARG PYTHON_IMAGE=python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

FROM ${PYTHON_IMAGE} AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
RUN python -m venv /opt/venv
COPY requirements.txt .
RUN /opt/venv/bin/python -m pip install --requirement requirements.txt

FROM ${PYTHON_IMAGE} AS runtime

ARG VERSION=dev
ARG VCS_REF=unknown
ARG SOURCE_URL=https://github.com/NaTo1000/Orcai25-watsonX-edition

LABEL org.opencontainers.image.title="Orcai25 WatsonX Edition" \
      org.opencontainers.image.description="AI security reference stack" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="${SOURCE_URL}" \
      org.opencontainers.image.licenses="LicenseRef-Proprietary"

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 10001 orcai \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin orcai

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=10001:10001 audit ./audit
COPY --chown=10001:10001 config ./config
COPY --chown=10001:10001 core ./core
COPY --chown=10001:10001 emergency_protocols ./emergency_protocols
COPY --chown=10001:10001 monitoring ./monitoring
COPY --chown=10001:10001 orcai_security.py .

USER 10001:10001

ENTRYPOINT ["python", "orcai_security.py"]
CMD ["health"]
