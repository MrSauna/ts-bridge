FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot code
COPY ts-bot.py .

# Set environment variables (override in docker run or compose)
ENV BOT_TOKEN=""
ENV TS_APIKEY=""
ENV TS_URL=""
ENV ALLOWED_GROUPS=""

# Run the bot
CMD ["python", "ts-bot.py"]