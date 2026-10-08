#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
D="$QA_WORK/helper"; mkdir -p "$D/classes" "$D/dex"
B="$ANDROID_SDK_ROOT/build-tools/35.0.0"
JAR="$ANDROID_SDK_ROOT/platforms/android-30/android.jar"
cat > "$D/AndroidManifest.xml" <<'XML'
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.desertrv.qa" android:versionCode="1" android:versionName="1">
  <uses-sdk android:minSdkVersion="30" android:targetSdkVersion="30" />
  <application android:label="Independent QA Input" android:debuggable="true" android:hasCode="true" />
  <instrumentation android:name=".TouchInstrumentation" android:targetPackage="com.desertrv.qa" />
</manifest>
XML
javac -source 8 -target 8 -bootclasspath "$JAR" -d "$D/classes" "$HERE/TouchInstrumentation.java"
jar cf "$D/classes.jar" -C "$D/classes" .
"$B/d8" --lib "$JAR" --min-api 30 --output "$D/dex" "$D/classes.jar"
"$B/aapt2" link -I "$JAR" --manifest "$D/AndroidManifest.xml" -o "$D/unsigned.apk"
(cd "$D/dex" && zip -q "$D/unsigned.apk" classes.dex)
"$B/zipalign" -p -f 4 "$D/unsigned.apk" "$D/aligned.apk"
# Ephemeral non-account test key; never touches or resigns the production APK.
keytool -genkeypair -keystore "$D/helper.jks" -storepass android -keypass android -alias qa -dname 'CN=Disposable QA' -keyalg RSA -validity 1 -noprompt
"$B/apksigner" sign --ks "$D/helper.jks" --ks-pass pass:android --out "$D/helper.apk" "$D/aligned.apk"
"$B/apksigner" verify "$D/helper.apk"
sha256sum "$D/helper.apk" > "$QA_OUT/helper-sha256.txt"
