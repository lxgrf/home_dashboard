FROM python:3.11-slim

# The Pimoroni Inky hardware library requires physical GPIO controls (RPi.GPIO and spidev).
# These require native C compilers during pip wheel negotiation.
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libi2c-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY viewer.py .

# Force Python stdout streaming so we can instantly see logs via docker
CMD ["python", "-u", "viewer.py"]
