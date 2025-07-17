# Phase 3: The Native macOS Server App

**Objective:** Create a lightweight, efficient, and native macOS menu bar application. This app will serve two primary purposes: 1) It will manage and run the core Python processing logic locally on the user's machine. 2) It will provide a native, real-time dashboard for monitoring the system, replacing the resource-heavy Next.js web dashboard.

---

### 1. Technology Stack

*   **Application Framework:** Swift with SwiftUI
*   **Application Type:** Menu Bar Agent (`LSUIElement` = `true`)
*   **Python Integration:** `Process` from Swift's `Foundation` framework to manage the Python backend as a subprocess.
*   **Inter-Process Communication (IPC):** A local-only WebSocket server running within the Python subprocess that the Swift UI connects to. This is simple, fast, and reuses existing WebSocket concepts.

---

### 2. High-Level Architecture

1.  **Swift App (Main Process):**
    *   The primary application bundle (`OrionServer.app`).
    *   Manages the entire lifecycle of the Python backend.
    *   Presents the UI (menu bar icon, menu, and dashboard windows).
    *   Connects to the local Python WebSocket for UI updates.
    *   Handles user authentication with Supabase.

2.  **Python Backend (Subprocess):**
    *   A standard Python process started by the Swift app.
    *   Runs the FastAPI/Celery application logic (from Phase 2, but configured for local execution).
    *   Instead of pulling from a cloud Redis queue, it will pull tasks from a local source (or directly process data if designed for single-user mode).
    *   Hosts a simple WebSocket server on a local port (e.g., `localhost:8001`) to stream logs and status updates to the Swift UI.

---

### 3. Implementation Details

1.  **Xcode Project Setup:**
    *   Create a new macOS App project in Xcode.
    *   In the `Info.plist` file, add the key `Application is agent (UIElement)` and set its value to `YES`. This hides the app from the Dock and makes it a menu bar app.
    *   Create a `MenuBarExtra` scene in your main `App.swift` file to define the menu bar icon and its content.

2.  **Python Lifecycle Management (`PythonServerManager.swift`):**
    *   Create a Swift class to handle the Python subprocess.
    *   **First-Time Setup:**
        *   On first launch, check if the Python virtual environment exists within the app's Application Support directory.
        *   If not, run a script that:
            1.  Creates a `venv` (`python3 -m venv ...`).
            2.  Installs dependencies from a bundled `requirements.txt` (`pip install -r ...`).
            3.  Downloads the ML models to the Application Support directory.
    *   **Process Control:**
        *   `start()`: Launches the Python `main.py` script using `Process`. It should capture the standard output and error streams to display in the native Log Viewer.
        *   `stop()`: Terminates the Python process gracefully (`process.terminate()`).
        *   `monitor()`: Periodically checks if the process is still running.

3.  **Native Dashboard UI (SwiftUI):**
    *   **Log Viewer:** A `ScrollView` containing `Text` views, populated by parsing the stdout from the Python subprocess.
    *   **Detection List:** A `List` view bound to an `@Published` array of `Detection` objects in a view model.
    *   **Network Flow:** A custom SwiftUI view using `HStack` and `VStack` with `Image(systemName:)` to replicate the flow visualizer.
    *   **Data Models:** Re-create the Pydantic models (`Detection`, `AnalysisResult`, etc.) as `Codable` Swift `struct`s.

4.  **Inter-Process Communication (IPC):**
    *   **Python Side:**
        *   Add a new local WebSocket endpoint to `server/main.py` (e.g., `/ws/local_dashboard`).
        *   Whenever the Python process logs something or has a status update, it sends a JSON message to all connected clients on this local WebSocket.
    *   **Swift Side:**
        *   Create a `LocalWebSocketManager.swift` class.
        *   Use `URLSession`'s `webSocketTask` to connect to `ws://localhost:8001/ws/local_dashboard`.
        *   Listen for incoming messages, decode the JSON into the Swift data models, and update the `@Published` properties in your view models to drive UI changes.

5.  **Cloud Integration:**
    *   Use the `supabase-swift` library to add a login flow to the macOS app's settings window.
    *   Once logged in, fetch the user's API key from your API (or allow them to paste it in).
    *   Store the API key securely in the macOS **Keychain**.
    *   The Python subprocess will need to be launched with this API key as an environment variable or argument so it can authenticate itself when interacting with the cloud API in the future.

---

### 4. User Experience

*   The menu bar icon should indicate the server's status (e.g., gray for off, spinning for starting, green for running, red for error).
*   The menu should provide options to "Start Server", "Stop Server", "Show Dashboard", "Settings", and "Quit".
*   The Dashboard window should be a native macOS window that feels fast and responsive.
