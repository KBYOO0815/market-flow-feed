#!/usr/bin/env bash
set -euo pipefail
export ANDROID_HOME="${ANDROID_HOME:-/usr/local/lib/android/sdk}"
export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"
export ANDROID_USER_HOME="$RUNNER_TEMP/android-user"
export ANDROID_AVD_HOME="$ANDROID_USER_HOME/avd"
mkdir -p "$ANDROID_AVD_HOME" evidence
test -c /dev/kvm
sudo chgrp "$(id -gn)" /dev/kvm
sudo chmod g+rw /dev/kvm
image='system-images;android-35;google_apis;x86_64'
sdkmanager --sdk_root="$ANDROID_HOME" 'platform-tools' 'emulator' "$image" > /dev/null
printf 'no\n' | avdmanager create avd --force --name news --package "$image"
emulator -avd news -no-window -no-audio -no-boot-anim -no-snapshot -gpu swiftshader_indirect > evidence/emulator.log 2>&1 &
trap 'adb emu kill || true' EXIT
timeout 300 bash -c 'adb wait-for-device; until [[ $(adb shell getprop sys.boot_completed | tr -d "\r") == 1 ]]; do sleep 3; done'
adb shell wm size 1080x2400
adb shell wm density 420
adb shell input keyevent 82
adb install "$1"
adb shell am start -W -n com.kbyoo0815.marketflow/.MainActivity
sleep 20
python3 scripts/emulate_news_screens.py
