FROM alpine:3.18

# By moving to pure Alpine 3.18, we natively keep linux/arm/v6 support.
# By explicitly downloading py3-numpy and py3-pillow via the apk package manager, 
# we instantly fetch pre-compiled binaries instead of forcing Pip to build C++ from source using Meson!
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-numpy \
    py3-pillow \
    py3-requests \
    gcc \
    musl-dev \
    python3-dev \
    linux-headers

WORKDIR /app

COPY viewer.py .

# We skip requirements.txt entirely so Pip doesn't attempt to compile strict Pillow/Numpy versions.
# --break-system-packages allows us to safely install strictly the hardware bindings alongside the apk libraries.
RUN pip3 install --no-cache-dir --break-system-packages inky RPi.GPIO spidev smbus2

# Force Python stdout streaming so we can instantly see logs via docker
CMD ["python3", "-u", "viewer.py"]
