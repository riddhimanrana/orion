#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="$ROOT_DIR/desktop/Orion Server.xcodeproj"
SCHEME="Orion Server"
DERIVED_DATA="$ROOT_DIR/.build/xcode/mac"
CONFIGURATION="${ORION_XCODE_CONFIGURATION:-Debug}"

echo "Building $SCHEME for macOS"
xcodebuild \
  -project "$PROJECT" \
  -scheme "$SCHEME" \
  -configuration "$CONFIGURATION" \
  -derivedDataPath "$DERIVED_DATA" \
  build

APP_PATH="$DERIVED_DATA/Build/Products/$CONFIGURATION/Orion Server.app"
open "$APP_PATH"
echo "Launched Orion Server from $APP_PATH"
