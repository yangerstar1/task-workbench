# Build the existing Environment.Dockerfile at its fixed official image digest first.
ARG BASE_IMAGE=desert-rv-environment:local
FROM ${BASE_IMAGE}
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg xdotool x11-utils openbox python3 python3-pil python3-yaml dbus \
    && rm -rf /var/lib/apt/lists/*
# Assert actual pinned-image contents BEFORE any credential enters a container.
# The wrapper's batchmode/new-Xvfb behavior is for official activation only.
RUN test "$UNITY_PATH" = /opt/unity \
    && test "$(cat "$UNITY_PATH/version")" = 6000.3.19f1 \
    && test -x "$UNITY_PATH/Editor/Unity" \
    && grep -q 'xvfb-run' /usr/bin/unity-editor \
    && grep -q -- '-batchmode' /usr/bin/unity-editor \
    && ! grep -q -- '-nographics' /usr/bin/unity-editor \
    && ffmpeg -hide_banner -h demuxer=x11grab 2>&1 | grep -q 'window_id' \
    && command -v Xvfb && command -v openbox && command -v xprop && command -v xdpyinfo
ENV LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
