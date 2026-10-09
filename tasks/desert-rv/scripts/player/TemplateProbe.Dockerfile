FROM unityci/editor@sha256:17406791cf1e438bea2dac20671668e05d83db5ed38c916744815db4584a8264
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/*
ENTRYPOINT ["/usr/bin/python3"]
