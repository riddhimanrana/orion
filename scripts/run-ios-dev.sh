#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="$ROOT_DIR/mobile/Orion Live.xcodeproj"
SCHEME="Orion Live"
DERIVED_DATA="$ROOT_DIR/.build/xcode/mobile"
BUNDLE_ID="riddhimanrana.orionlive"

DESTINATION="${ORION_IOS_DESTINATION:-platform=iOS Simulator,name=iPhone 17}"
CONFIGURATION="${ORION_XCODE_CONFIGURATION:-Debug}"

echo "Building $SCHEME for $DESTINATION"
xcodebuild \
  -project "$PROJECT" \
  -scheme "$SCHEME" \
  -configuration "$CONFIGURATION" \
  -destination "$DESTINATION" \
  -derivedDataPath "$DERIVED_DATA" \
  build

if [[ "$DESTINATION" == *"iOS Simulator"* ]]; then
  DEVICE_NAME="${ORION_IOS_SIMULATOR_NAME:-iPhone 17}"
  DEVICE_ID="$(xcrun simctl list devices available | awk -v name="$DEVICE_NAME" '
    $0 ~ "^[[:space:]]*" name " \\(" && $0 ~ /Shutdown|Booted/ {
      gsub(/[()]/, "", $0)
      print $(NF-1)
      exit
    }
  ')"
  if [[ -z "$DEVICE_ID" ]]; then
    echo "Could not find available simulator named $DEVICE_NAME" >&2
    exit 1
  fi

  APP_PATH="$DERIVED_DATA/Build/Products/$CONFIGURATION-iphonesimulator/Orion Live.app"
  SIMULATOR_APP="$(xcode-select -p)/Applications/Simulator.app"
  xcrun simctl boot "$DEVICE_ID" 2>/dev/null || true
  xcrun simctl bootstatus "$DEVICE_ID" -b
  if [[ -d "$SIMULATOR_APP" ]]; then
    open "$SIMULATOR_APP"
  else
    open -a Simulator 2>/dev/null || true
  fi
  xcrun simctl install "$DEVICE_ID" "$APP_PATH"
  xcrun simctl launch "$DEVICE_ID" "$BUNDLE_ID"
  echo "Launched Orion Live on $DEVICE_NAME ($DEVICE_ID)"
else
  echo "Built for physical iOS destination."
  echo "For Riddhiman's iPhone 12, connect/unlock device then run:"
  echo "ORION_IOS_DESTINATION='platform=iOS,name=Riddhiman’s iPhone 12' bun run dev:mobile"
  echo "Open Xcode if signing or device trust needs interactive approval."
fi
