FROM python:3.11-slim

# Working directory
WORKDIR /app

# Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source code
COPY . .

# Volume for persistent SQLite DB
VOLUME ["/data"]

# Start bot
CMD ["python", "bot.py"]
