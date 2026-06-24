# Orion Monorepo

Orion is an object-centric memory world-model for real-time vision intelligence, structured as a single monorepo with multiple product surfaces.

## Project Structure

* [mobile/](file:///Users/riddhiman.rana/Desktop/Coding/orion/mobile) — iOS Client App (Camera capture, frame proposals, WebRTC video streaming)
* [desktop/](file:///Users/riddhiman.rana/Desktop/Coding/orion/desktop) — macOS Client App / Menu Bar interface
* [website/](file:///Users/riddhiman.rana/Desktop/Coding/orion/website) — Next.js frontend website / Dashboard interface
* [signal/](file:///Users/riddhiman.rana/Desktop/Coding/orion/signal) — Node.js/Bun WebRTC signaling service
* [server/](file:///Users/riddhiman.rana/Desktop/Coding/orion/server) — Python backend server (Gemma-4 reasoning, PyTorch YOLO26x detection on MPS, FastVLM)
* [research/](file:///Users/riddhiman.rana/Desktop/Coding/orion/research) — Python research pipeline, evaluation suites, and experiments

---

## Development Environment Setup

### 1. Prerequisites
Ensure you have the following installed on your Mac:
* [Bun](https://bun.sh/) (version 1.2.0 or later)
* [uv](https://github.com/astral-sh/uv) (fast Python package installer)
* Python 3.11
* Xcode (with command line tools)

### 2. Python Virtual Environment Setup
Since both `research/` and `server/` share heavy deep-learning dependencies, they run on a shared virtual environment managed inside `research/`:

```bash
# Navigate to the research directory
cd research

# Create a virtual environment using uv
uv venv

# Install the research package and all its dependencies in editable mode
uv pip install -e .

# Install the server dependencies into the same environment
uv pip install -r ../server/requirements.txt
```

---

## Running Product Surfaces

Use the unified root scripts from [package.json](file:///Users/riddhiman.rana/Desktop/Coding/orion/package.json):

### Web Dashboard & Website
```bash
bun run dev:web
```

### WebRTC Signaling Server
```bash
bun run dev:signal
```

### Orion Python Server (Gemma-4 + YOLO26x + FastVLM)
```bash
bun run dev:server
```

### iOS Mobile Client (iPhone 17 Simulator)
```bash
bun run dev:mobile
```

### macOS Desktop Client
```bash
bun run dev:mac
```

### Research Pipeline CLI
```bash
bun run dev:research -- --help
```

---

## Production / Build Checks

```bash
bun run build:web
bun run build:signal
bun run build:mobile
bun run build:mac
```

## VS Code Integration

Open [Orion.code-workspace](file:///Users/riddhiman.rana/Desktop/Coding/orion/.code-workspace) in VS Code. It is pre-configured with workspace recommendations, settings for Copilot, SweetPad, and xcodebuild server integrations.

## Branching Model

* `main` — Stable production-ready baseline.
* `development` — Active integration branch for day-to-day development.
