
FROM python:3.14-slim-bookworm

ARG DEBIAN_FRONTEND=noninteractive


# Combine package updates, installations, downloads, and cleanups into a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    git \
    libicu-dev \
    socat \
    openssh-client \
    tree \
    wget \
    unzip \
    xz-utils \
 && curl -LsSf https://astral.sh/uv/install.sh | sh \
 && curl -fsSL https://claude.ai/install.sh | bash \
 && curl -fsSL https://bun.com/install | bash \
 && apt-get install -y --no-install-recommends \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* /tmp/*.deb

# The Docker CLI, statically linked, pinned to the host daemon's version.
# Aspire's DCP does NOT talk to the socket itself -- it shells out to this
# binary. Without it `dcp info` reports the container runtime as
# installed:false / running:false and no container resource ever starts,
# however correct DOCKER_HOST is.
ARG DOCKER_CLI_VERSION=29.8.0
RUN arch="$(uname -m)" \
 && curl -fsSL "https://download.docker.com/linux/static/stable/${arch}/docker-${DOCKER_CLI_VERSION}.tgz" \
    | tar -xzf - --strip-components=1 -C /usr/local/bin docker/docker \
 && docker --version


WORKDIR /root

ENV PATH="/root/.local/bin:${PATH}"
CMD ["sleep", "infinity"]


