#!/bin/bash

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"
SERVER_DIR="$PROJECT_ROOT/server"

print_status() {
    echo -e "${YELLOW}[*] $1${NC}"
}

print_success() {
    echo -e "${GREEN}[+] $1${NC}"
}

print_error() {
    echo -e "${RED}[-] $1${NC}"
}

NEXTJS_PID=""
PYTHON_PID=""

# --- Signal Handling for Graceful Shutdown ---
cleanup() {
    echo
    print_status "Caught interrupt signal. Cleaning up..."
    if [ ! -z "$PYTHON_PID" ]; then
        print_status "Stopping Python server (PID: $PYTHON_PID)..."
        kill $PYTHON_PID 2>/dev/null
        wait $PYTHON_PID 2>/dev/null
    fi
    if [ ! -z "$NEXTJS_PID" ]; then
        print_status "Stopping Next.js server (PID: $NEXTJS_PID)..."
        kill $NEXTJS_PID 2>/dev/null
        wait $NEXTJS_PID 2>/dev/null
    fi
    print_success "Cleanup complete. Exiting."
    exit 0
}

trap cleanup SIGINT SIGTERM

# --- Prerequisite Checks ---
print_status "Performing prerequisite checks..."
# Check for Apple Silicon
if [[ $(uname -m) != "arm64" ]]; then # uname -m is more reliable for Apple Silicon
    print_error "This server is optimized for Apple Silicon (M1/M2/M3) hardware (arm64 architecture)."
    # exit 1 # Commenting out to allow running on other arch for dev, but MLX won't work
fi

# Check Python version (e.g., 3.10+)
PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
if [[ "$PYTHON_MAJOR" -lt 3 ]] || ([[ "$PYTHON_MAJOR" -eq 3 ]] && [[ "$PYTHON_MINOR" -lt 10 ]]); then
    print_error "Python 3.10 or higher is required. Found $(python3 --version)."
    exit 1
fi
print_success "Python version check passed."

# --- Virtual Environment Setup ---
VENV_DIR="$SERVER_DIR/venv"
if [ ! -d "$VENV_DIR" ]; then
    print_status "Creating Python virtual environment in $VENV_DIR..."
    python3 -m venv "$VENV_DIR" || { print_error "Failed to create virtual environment."; exit 1; }
    print_success "Virtual environment created."
else
    print_status "Virtual environment already exists at $VENV_DIR."
fi

print_status "Activating virtual environment..."
source "$VENV_DIR/bin/activate" || { print_error "Failed to activate virtual environment."; exit 1; }
print_success "Virtual environment activated."

# --- Install Dependencies ---
print_status "Installing/updating Python dependencies from $SERVER_DIR/requirements.txt..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip || { print_error "Failed to upgrade pip."; exit 1; }
"$VENV_DIR/bin/python" -m pip install -r "$SERVER_DIR/requirements.txt" || { print_error "Failed to install dependencies."; exit 1; }
print_success "Dependencies installed."

# --- Model Directory and Acquisition ---
WEIGHTS_DIR="$SERVER_DIR/weights"
GEMMA_MODEL_DIR="$WEIGHTS_DIR/gemma-3-1b-it-4bit"
YOLO_MODEL_DIR="$WEIGHTS_DIR/yolov11n"
FASTVLM_MODEL_DIR="$WEIGHTS_DIR/fastvlm-0.5b"

print_status "Creating model directories if they don't exist..."
mkdir -p "$GEMMA_MODEL_DIR"
mkdir -p "$YOLO_MODEL_DIR"
mkdir -p "$FASTVLM_MODEL_DIR"
print_success "Model directories ensured."

# Gemma-1b Model Check & Download
print_status "Checking for Gemma-1b model..."
if [ ! -f "$GEMMA_MODEL_DIR/model.safetensors" ] && [ ! -f "$GEMMA_MODEL_DIR/weights.safetensors" ]; then
    print_status "Gemma-1b model not found. Attempting to download..."
    if command -v huggingface-cli &> /dev/null; then
        huggingface-cli download mlx-community/gemma-3-1b-it-4bit --local-dir "$GEMMA_MODEL_DIR" --local-dir-use-symlinks False --quiet
        if [ $? -eq 0 ]; then
            print_success "Gemma-1b model downloaded successfully."
        else
            print_error "Failed to download Gemma-1b model."
        fi
    else
        print_error "huggingface-cli not found. Cannot download Gemma-1b model."
    fi
else
    print_success "Gemma-1b model found."
fi

# YOLOv11n Model Check & Download
print_status "Checking for YOLOv11n model..."
if [ ! -d "$YOLO_MODEL_DIR/yolo11n.mlpackage" ]; then
    print_status "YOLOv11n model not found. Attempting to download..."
    YOLO_URL="https://github.com/RiddhimanRana/yolo11n-mlx/archive/refs/heads/main.zip"
    YOLO_ZIP_PATH="$WEIGHTS_DIR/yolo11n.zip"
    curl -L "$YOLO_URL" -o "$YOLO_ZIP_PATH"
    unzip -q "$YOLO_ZIP_PATH" -d "$WEIGHTS_DIR"
    # Move contents from the unzipped folder to the target directory
    mv "$WEIGHTS_DIR/yolo11n-mlx-main/yolo11n.mlpackage" "$YOLO_MODEL_DIR/"
    rm -rf "$WEIGHTS_DIR/yolo11n-mlx-main" "$YOLO_ZIP_PATH"
    print_success "YOLOv11n model downloaded and extracted."
else
    print_success "YOLOv11n model found."
fi

# FastVLM Model Check & Download
print_status "Checking for FastVLM model..."
if [ ! -f "$FASTVLM_MODEL_DIR/model.safetensors" ]; then
    print_status "FastVLM model not found. Attempting to download..."
    FASTVLM_URL="https://ml-site.cdn-apple.com/datasets/fastvlm/llava-fastvithd_0.5b_stage3_llm.fp16.zip"
    FASTVLM_ZIP_PATH="$WEIGHTS_DIR/fastvlm.zip"
    curl -L "$FASTVLM_URL" -o "$FASTVLM_ZIP_PATH"
    unzip -q "$FASTVLM_ZIP_PATH" -d "$WEIGHTS_DIR"
    # The zip extracts to a folder named after the model, move its contents
    mv "$WEIGHTS_DIR/llava-fastvithd_0.5b_stage3_llm.fp16"/* "$FASTVLM_MODEL_DIR/"
    rm -rf "$WEIGHTS_DIR/llava-fastvithd_0.5b_stage3_llm.fp16" "$FASTVLM_ZIP_PATH"
    print_success "FastVLM model downloaded and extracted."
else
    print_success "FastVLM model found."
fi


# --- Environment File (.env) ---
ENV_FILE="$SERVER_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    print_status "Creating default .env file at $ENV_FILE..."
    cat > "$ENV_FILE" << EOL
# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=true
LOG_LEVEL=INFO

# Model paths (primarily for reference if ModelManager uses config.py directly)
LLM_MODEL_PATH="weights/gemma-3-1b-it-4bit/"
YOLO_MODEL_PATH="weights/yolov11n/"
FASTVLM_MODEL_PATH="weights/fastvlm-0.5b/"
PROCESSING_MODE="split" # "split" or "full"
EOL
    print_success ".env file created."
else
    print_status ".env file already exists at $ENV_FILE."
fi

# --- Launch Next.js Dashboard (Frontend) ---
print_status "Attempting to start Next.js development server..."
if [ -f "$PROJECT_ROOT/bun.lock" ] || command -v bun &> /dev/null; then
    if [ -f "$PROJECT_ROOT/package.json" ]; then
        print_status "Found bun.lock or bun command, and package.json. Starting Next.js with 'bun dev' in the background."
        cd "$PROJECT_ROOT" || { print_error "Failed to change directory to $PROJECT_ROOT for Next.js."; }
        bun dev &
        NEXTJS_PID=$!
        print_success "Next.js 'bun dev' started in background (PID: $NEXTJS_PID). Output will be in its own stream."
        cd "$PROJECT_ROOT"
    else
        print_warning "bun detected, but no package.json found in $PROJECT_ROOT. Skipping Next.js start."
    fi
elif command -v npm &> /dev/null; then
    if [ -f "$PROJECT_ROOT/package.json" ]; then
        print_status "Found npm and package.json. Starting Next.js with 'npm run dev' in the background."
        cd "$PROJECT_ROOT" || { print_error "Failed to change directory to $PROJECT_ROOT for Next.js."; }
        npm run dev &
        NEXTJS_PID=$!
        print_success "Next.js 'npm run dev' started in background (PID: $NEXTJS_PID). Output will be in its own stream."
        cd "$PROJECT_ROOT"
    else
        print_warning "npm detected, but no package.json found in $PROJECT_ROOT. Skipping Next.js start."
    fi
else
    print_warning "Neither bun nor npm found, or no package.json in $PROJECT_ROOT. Cannot start Next.js development server automatically."
    print_status "Please start it manually in a separate terminal (e.g., by navigating to $PROJECT_ROOT and running 'bun dev' or 'npm run dev')."
fi

# --- Display Connection Info for iOS App ---
print_status "Attempting to determine local IP for iOS app connection..."
LOCAL_IP_EN0=$(ipconfig getifaddr en0)
PYTHON_SERVER_PORT_FROM_ENV=$(grep -E '^PORT=' "$SERVER_DIR/.env" | cut -d '=' -f2)
PYTHON_SERVER_PORT=${PYTHON_SERVER_PORT_FROM_ENV:-8000}

if [ -n "$LOCAL_IP_EN0" ]; then
    print_success "Your Mac's local IP address (en0 - Wi-Fi) appears to be: $LOCAL_IP_EN0"
    print_status "Configure your iOS app (ServerConfig.host) to connect to: ws://$LOCAL_IP_EN0:$PYTHON_SERVER_PORT/ios"
else
    LOCAL_IP_EN1=$(ipconfig getifaddr en1) # Try en1 as a fallback
    if [ -n "$LOCAL_IP_EN1" ]; then
        print_success "Your Mac's local IP address (en1) appears to be: $LOCAL_IP_EN1"
        print_status "Configure your iOS app (ServerConfig.host) to connect to: ws://$LOCAL_IP_EN1:$PYTHON_SERVER_PORT/ios"
    else
        print_warning "Could not automatically determine local IP for en0 or en1."
        print_status "Please check your Mac's System Settings > Network to find your local IP address."
        print_status "Then, configure your iOS app (ServerConfig.host) to connect to: ws://YOUR_MAC_IP_ADDRESS:$PYTHON_SERVER_PORT/ios"
    fi
fi
echo # Add a blank line for readability

# --- Launch Server (Python Backend) ---
print_status "Starting Orion Server (Python Backend)..."
cd "$SERVER_DIR" || { print_error "Failed to change directory to $SERVER_DIR"; exit 1; }
"$VENV_DIR/bin/python" main.py &
PYTHON_PID=$!
wait $PYTHON_PID

print_success "Orion Server script finished."

# Optional: Clean up background Next.js process if Python server exits
if [ ! -z "$NEXTJS_PID" ]; then
    print_status "Attempting to stop Next.js server (PID: $NEXTJS_PID)..."
    kill $NEXTJS_PID 2>/dev/null
    wait $NEXTJS_PID 2>/dev/null
fi
