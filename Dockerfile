FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system zeus \
    && adduser --system --ingroup zeus --home /home/zeus zeus \
    && mkdir -p /home/zeus/.zeus \
    && chown -R zeus:zeus /home/zeus

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m pip install --upgrade pip \
    && python -m pip install .

USER zeus
WORKDIR /home/zeus

CMD ["zeus", "status", "--json"]
