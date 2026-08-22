# syntax=docker/dockerfile:1
# Builds a sideload-signed debug APK of the citizen WebView shell.
# SDK + JDK live in the image so the laptop only needs Docker (same rule as run.py).

FROM eclipse-temurin:17-jdk-jammy AS sdk

ENV ANDROID_HOME=/opt/android-sdk
ENV ANDROID_SDK_ROOT=/opt/android-sdk
ENV GRADLE_VERSION=8.7
ENV PATH="${PATH}:${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools:/opt/gradle-${GRADLE_VERSION}/bin"

RUN apt-get update \
    && apt-get install -y --no-install-recommends wget unzip \
    && rm -rf /var/lib/apt/lists/*

RUN wget -q https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip -O /tmp/gradle.zip \
    && unzip -q /tmp/gradle.zip -d /opt \
    && rm /tmp/gradle.zip

RUN mkdir -p ${ANDROID_HOME}/cmdline-tools \
    && wget -q https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -O /tmp/cmd.zip \
    && unzip -q /tmp/cmd.zip -d /tmp/cmd \
    && mv /tmp/cmd/cmdline-tools ${ANDROID_HOME}/cmdline-tools/latest \
    && rm -rf /tmp/cmd /tmp/cmd.zip

# Pre-accept the SDK licence so the build is non-interactive.
RUN mkdir -p ${ANDROID_HOME}/licenses \
    && printf '%s\n' "24333f8a63b6825ea9c5514f83c2829b004d1fee" > ${ANDROID_HOME}/licenses/android-sdk-license \
    && sdkmanager --sdk_root=${ANDROID_HOME} \
        "platforms;android-34" \
        "build-tools;34.0.0" \
        "platform-tools"

FROM sdk AS build
WORKDIR /src
COPY . .
ARG CITIZEN_PWA_URL=https://setucitizen.vercel.app/
ENV CITIZEN_PWA_URL=${CITIZEN_PWA_URL}
RUN gradle assembleDebug --no-daemon \
    && find app/build/outputs -name '*.apk' -print -exec ls -la {} \; \
    && APK=app/build/outputs/apk/debug/app-debug.apk \
    && ALIGNED=/tmp/aligned.apk \
    && SIGNED=/tmp/SETU-citizen.apk \
    && ${ANDROID_HOME}/build-tools/34.0.0/zipalign -f 4 "${APK}" "${ALIGNED}" \
    && KS="${HOME}/.android/debug.keystore" \
    && if [ ! -f "${KS}" ]; then \
         keytool -genkeypair -v -keystore "${KS}" -storepass android -alias androiddebugkey \
           -keypass android -keyalg RSA -keysize 2048 -validity 10000 \
           -dname "CN=Android Debug,O=Android,C=US"; \
       fi \
    && ${ANDROID_HOME}/build-tools/34.0.0/apksigner sign \
         --ks "${KS}" --ks-pass pass:android --key-pass pass:android \
         --ks-key-alias androiddebugkey \
         --out "${SIGNED}" "${ALIGNED}" \
    && ${ANDROID_HOME}/build-tools/34.0.0/apksigner verify --verbose "${SIGNED}" \
    && unzip -l "${SIGNED}" | head -n 40 \
    && ls -la "${SIGNED}"

FROM scratch AS export
COPY --from=build /tmp/SETU-citizen.apk /SETU-citizen.apk
