# Phase 4: iOS App Modernization

**Objective:** Overhaul the Orion iOS application to align with the new cloud-native architecture. This involves removing the direct WebSocket dependency, implementing a robust authentication system with Supabase, and shifting to a "fire-and-forget" data submission model using the new public API.

---

### 1. Technology Stack

*   **Application Framework:** Swift & SwiftUI
*   **Authentication:** `supabase-swift` library
*   **Networking:** Swift's native `URLSession` with `async/await`
*   **Secure Storage:** iOS Keychain for storing API keys and auth tokens.

---

### 2. Authentication and User Flow

1.  **Onboarding/Login Screen:**
    *   When the app first launches, it must check for a valid Supabase session.
    *   If no session exists, present a new `LoginView.swift`.
    *   This view will contain fields for email/password and buttons for "Sign in with Google" and "Sign in with Apple".

2.  **Authentication Logic (`AuthManager.swift`):**
    *   Create a new `AuthManager` class as an `ObservableObject`.
    *   Use the `supabase-swift` library to implement:
        *   `signInWithEmail(email:, password:)`
        *   `signUp(email:, password:)`
        *   `signInWithApple()`
        *   `signInWithGoogle()`
        *   `signOut()`
    *   Upon successful login, the app must securely store the session information provided by Supabase.

3.  **API Key Management:**
    *   After login, the app needs an API key to communicate with `api.orion.riddhimanrana.com`.
    *   **Recommended Flow:** The iOS app should make an authenticated request to a new endpoint on the *website's* API (from Phase 1), e.g., `GET /api/keys/get-or-create`, which returns a valid API key for the user.
    *   **Keychain Storage:** Store the retrieved API key securely in the iOS Keychain. Never store it in `UserDefaults`.

---

### 3. Networking Layer Refactor

The existing `WebSocketManager.swift` will be completely replaced.

1.  **Create `APIService.swift`:**
    *   This new class will be responsible for all communication with your public API.
    *   It will not hold a persistent connection. Each method will create and manage its own `URLSessionDataTask`.

2.  **Implement API Methods:**
    *   **`sendFrame(frameData: FrameDataMessage) async throws -> String`**
        1.  Retrieve the API key from the Keychain.
        2.  Construct a `URLRequest` for `POST /v1/frame`.
        3.  Set the `Content-Type` header to `application/json`.
        4.  Set the `Authorization` header to `Bearer <API_KEY>`.
        5.  Encode the `frameData` object to JSON for the request body.
        6.  Use `URLSession.shared.data(for: request)` with `async/await` to execute the request.
        7.  Check for a `202 Accepted` status code. If not, throw an error.
        8.  Decode the JSON response to get the `task_id` and return it.

    *   **`getAnalysisResult(taskId: String) async throws -> AnalysisResult`** (Optional, for future use)
        *   Similar to `sendFrame`, but makes a `GET` request to `/v1/result/{task_id}`.

---

### 4. Core Logic and UI Updates

1.  **Update `CameraManager.swift`:**
    *   The `detectionCallback` will no longer interact with a WebSocket manager.
    *   Instead, it will now call `APIService.sendFrame`.
    *   Crucially, the app **should not** `await` the result of this call in a way that blocks the camera processing thread. It should be a "fire-and-forget" operation.

    ```swift
    // Inside CameraManager's detection callback
    cameraManager.setDetectionCallback { imageData, detections, vlmDescription, vlmConfidence in
        // ... create FrameDataMessage ...
        
        // Launch a new Task to send the data without blocking the camera thread
        Task {
            do {
                let taskId = try await apiService.sendFrame(frameData: frameData)
                Logger.shared.log("Successfully submitted frame, task ID: \(taskId)", category: .network)
            } catch {
                Logger.shared.log("Failed to send frame: \(error)", level: .error, category: .network)
            }
        }
    }
    ```

2.  **UI Changes:**
    *   **Remove Real-time Analysis:** The main camera view will no longer receive real-time analysis results from the server. The primary purpose of the iOS app is now data *capture and submission*. The analysis will be viewed on the Mac app or a future web dashboard.
    *   **Add Profile/Settings Tab:**
        *   Create a new tab in the main `TabView`.
        *   Display the logged-in user's email.
        *   Include a "Log Out" button that calls `AuthManager.signOut()`.
        *   Show the current status of the API connection (e.g., "Connected to api.orion.riddhimanrana.com").
