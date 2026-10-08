# Official GameCI image is supplied at its reviewed immutable digest by workflow.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
RUN apt-get update && apt-get install -y --no-install-recommends libgl1-mesa-dri libglx-mesa0 mesa-utils xauth \
    && rm -rf /var/lib/apt/lists/*
ENV LIBGL_ALWAYS_SOFTWARE=1
ENV GALLIUM_DRIVER=llvmpipe
# Fail before secrets are used if the expected official Xvfb wrapper is absent.
RUN command -v xvfb-run && grep -q 'xvfb-run' /usr/bin/unity-editor \
    && ! grep -q -- '-nographics' /usr/bin/unity-editor \
    && xvfb-run -a glxinfo -B | grep -qi llvmpipe
