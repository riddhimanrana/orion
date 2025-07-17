Phase 3: The Native macOS Server App

  Goal: Replace the resource-intensive Next.js dashboard with a lightweight, native macOS menu bar application that also runs the core Python processing logic.

   1. Technology Stack:
       * Application: Swift and SwiftUI for the native UI.
       * Python Integration: A bundled Python environment or a managed subprocess.

   2. Execution Steps:
       * macOS App Foundation:
           * Create a new Xcode project for a macOS app, configured to run as a menu bar agent.
       * Python Backend Integration:
           * The Swift app will be responsible for managing and running the Python server code from the server/ directory.
           * On first launch, the app can automate the setup from start.sh: create a virtual environment, install dependencies, and download models.
           * The Swift app will launch the Python processing logic as a background subprocess.
           * Inter-Process Communication (IPC): Use a local mechanism for the Swift UI to get real-time data from the Python subprocess (e.g., a local WebSocket, a
             simple REST API on localhost, or reading from a structured log file).
       * Native Dashboard UI:
           * Re-implement the UI components from the Next.js dashboard (DetectionList, LogViewer, LLMReasoningTree, etc.) in SwiftUI.
           * These views will be populated with data received from the local Python subprocess via IPC, ensuring high performance and low resource usage.
       * Cloud Integration:
           * The Mac app will need to authenticate the user via Supabase (using the Swift SDK).
           * It will use the user's API key to communicate with api.orion.riddhimanrana.com to fetch tasks and report results if needed in the future.
