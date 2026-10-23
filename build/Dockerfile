FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        binutils \
        ca-certificates \
        curl \
        file \
        fonts-dejavu-core \
        libgl1 \
        patchelf \
        python3 \
        python3-dev \
        python3-pip \
        python3-tk \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir "pyinstaller==6.11.1" "pillow==10.4.0"

WORKDIR /src
COPY . /src
RUN bash build/build_inside.sh
