# Official Android image observed in successful baseline build job 113380892675.
FROM unityci/editor@sha256:1e98c949ff728e6ff627b5c55ef65975125a6dc47cf27060601b79a141cc8692
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-dri libglx-mesa0 mesa-utils xauth python3 python3-pil python3-yaml dbus \
    && rm -rf /var/lib/apt/lists/*
ENV LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
# The successful baseline builder installed this same platform after pulling the image.
# Use its bundled official sdkmanager, with closed stdin; never auto-accept new licenses.
RUN JAVA_HOME=/opt/unity/Editor/Data/PlaybackEngines/AndroidPlayer/OpenJDK \
    timeout 600 /opt/unity/Editor/Data/PlaybackEngines/AndroidPlayer/SDK/cmdline-tools/16.0/bin/sdkmanager \
    --sdk_root=/opt/unity/Editor/Data/PlaybackEngines/AndroidPlayer/SDK 'platforms;android-35' </dev/null \
    && test -f /opt/unity/Editor/Data/PlaybackEngines/AndroidPlayer/SDK/platforms/android-35/android.jar
# Check the actual module and bundled toolchain before any license credentials enter.
RUN test "$UNITY_PATH" = /opt/unity \
    && test "$(cat /opt/unity/version)" = 6000.3.19f1 \
    && test -x /opt/unity/Editor/Unity \
    && test -f /opt/unity/Editor/Data/PlaybackEngines/AndroidPlayer/UnityEditor.Android.Extensions.dll \
    && test -x /opt/unity/Editor/Data/PlaybackEngines/AndroidPlayer/OpenJDK/bin/java \
    && test -d /opt/unity/Editor/Data/PlaybackEngines/AndroidPlayer/NDK \
    && test -x /opt/unity/Editor/Data/PlaybackEngines/AndroidPlayer/SDK/build-tools/36.0.0/aapt \
    && test -x /opt/unity/Editor/Data/PlaybackEngines/AndroidPlayer/SDK/build-tools/36.0.0/apksigner \
    && grep -q 'xvfb-run' /usr/bin/unity-editor \
    && ! grep -q -- '-nographics' /usr/bin/unity-editor \
    && xvfb-run -a glxinfo -B | grep -qi llvmpipe
