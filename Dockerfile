FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY regdet ./regdet
COPY prompts ./prompts
COPY data/golden_dataset.json ./data/golden_dataset.json
COPY baselines ./baselines
# Config comes from environment variables at run time:
#   OPENAI_API_KEY, SLACK_WEBHOOK_URL, WARN_THRESHOLD, CRIT_THRESHOLD, PROVIDER ...
ENTRYPOINT ["python", "-m", "regdet"]
CMD ["run", "--prompt", "prompts/v1.yaml", "--baseline", "baselines/baseline.json", "--out", "/app/reports"]
