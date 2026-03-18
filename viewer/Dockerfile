FROM python:3.9-alpine

# The Pimoroni Inky hardware library requires physical GPIO controls (RPi.GPIO and spidev).
# We use apk (Alpine) since it natively supports the linux/arm/v6 architecture matrix.
RUN apk add --no-cache \
    gcc \
    musl-dev \
    python3-dev \
    linux-headers \
    zlib-dev \
    jpeg-dev \
    freetype-dev

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY viewer.py .

# Force Python stdout streaming so we can instantly see logs via docker
CMD ["python", "-u", "viewer.py"]
