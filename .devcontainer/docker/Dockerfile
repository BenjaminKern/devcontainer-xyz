#============================================================================
# Base Stage: Minimal runtime environment
#============================================================================
ARG IMAGE_NAME=ubuntu
ARG IMAGE_TAG=24.04

FROM ${IMAGE_NAME}:${IMAGE_TAG} AS base

ARG USER_UID=1000
ARG USER_GID=1000
ARG USERNAME=developer

ARG YQ_VERSION=4.44.3
ARG UV_VERSION=0.9.17
ARG BAZELISK_VERSION=1.27.0

LABEL org.opencontainers.image.title="devcontainer-xyz" \
      org.opencontainers.image.version="${IMAGE_TAG}"

ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8

COPY packages.yml /tmp/

RUN <<EOF
set -eux

ARCH=$(uname -m)
case ${ARCH} in
    x86_64)  ARCH_SUFFIX="amd64" ;;
    aarch64) ARCH_SUFFIX="arm64" ;;
    *)       echo "Unsupported architecture: ${ARCH}" && exit 1 ;;
esac

# Set non-interactive frontend for apt
export DEBIAN_FRONTEND=noninteractive

# Single apt-get update for all base packages
apt-get update -qq
apt-get install -y --no-install-recommends \
    ca-certificates curl git locales sudo

# Install yq
curl -fsSL "https://github.com/mikefarah/yq/releases/download/v${YQ_VERSION}/yq_linux_${ARCH_SUFFIX}" \
    -o /usr/local/bin/yq && chmod +x /usr/local/bin/yq

# Install custom base packages
yq -r '.base.packages // [] | .[]' /tmp/packages.yml | \
    xargs -r apt-get install -y --no-install-recommends

rm -rf /var/lib/apt/lists/*
locale-gen

# Install uv
curl -fsSL "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-${ARCH}-unknown-linux-gnu.tar.gz" \
    | tar xzf - -C /usr/local/bin --strip-components=1 \
        uv-${ARCH}-unknown-linux-gnu/uv \
        uv-${ARCH}-unknown-linux-gnu/uvx

# Install Bazelisk
curl -fsSL "https://github.com/bazelbuild/bazelisk/releases/download/v${BAZELISK_VERSION}/bazelisk-linux-${ARCH_SUFFIX}" \
    -o /usr/local/bin/bazelisk && chmod +x /usr/local/bin/bazelisk
ln -s /usr/local/bin/bazelisk /usr/local/bin/bazel

# uvx-shim for lazy Python tool loading
cat > /usr/local/bin/uvx-shim << 'SHIM'
#!/usr/bin/env bash
set -euo pipefail
exec uvx "$(basename "$0")" "$@"
SHIM
chmod +x /usr/local/bin/uvx-shim

yq -r '.base.python_tools // [] | .[]' /tmp/packages.yml | \
    xargs -I {} ln -sf /usr/local/bin/uvx-shim /usr/local/bin/{}

# CI user (UID 1001)
groupadd --gid 1001 github-action-bot
useradd --uid 1001 --gid 1001 -m -s /bin/bash github-action-bot

# Dev user - rename existing UID/GID if present, otherwise create
if getent group ${USER_GID} >/dev/null 2>&1; then
    groupmod -n ${USERNAME} $(getent group ${USER_GID} | cut -d: -f1) 2>/dev/null || true
else
    groupadd --gid ${USER_GID} ${USERNAME}
fi

if getent passwd ${USER_UID} >/dev/null 2>&1; then
    usermod -l ${USERNAME} -d /home/${USERNAME} -m $(getent passwd ${USER_UID} | cut -d: -f1) 2>/dev/null || true
else
    useradd --uid ${USER_UID} --gid ${USER_GID} -m -s /bin/bash ${USERNAME}
fi

echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME}
chmod 0440 /etc/sudoers.d/${USERNAME}

mkdir -p /workspace /home/${USERNAME}/.{config,cache,local/share,local/state}
chown -R ${USER_UID}:${USER_GID} /workspace /home/${USERNAME}
EOF

CMD ["sleep", "infinity"]

#============================================================================
# DevEnv Stage: Development tools
#============================================================================
FROM base AS devenv
ARG USERNAME

RUN <<EOF
set -eux

export DEBIAN_FRONTEND=noninteractive

apt-get update
yq -r '.devenv.packages // [] | .[]' /tmp/packages.yml | \
    xargs -r apt-get install -y --no-install-recommends

yq -r '.devenv.python_tools // [] | .[]' /tmp/packages.yml | \
    xargs -I {} ln -sf /usr/local/bin/uvx-shim /usr/local/bin/{}

rm -rf /var/lib/apt/lists/* /tmp/packages*
EOF

USER ${USERNAME}
WORKDIR /workspace
