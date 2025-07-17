Phase 4: iOS App Modernization

  Goal: Update the iOS app to use the new cloud API and integrate the user authentication system.

   1. Technology Stack:
       * Application: Swift and SwiftUI (existing).
       * Authentication: Supabase Swift SDK.

   2. Execution Steps:
       * Implement Authentication:
           * Build Login/Signup screens using SwiftUI.
           * Use the Supabase SDK to handle user authentication and session management.
           * Securely store the user's auth token and API key in the iOS Keychain.
       * Overhaul Networking Layer:
           * Remove the WebSocketManager.
           * Create a new APIService class to handle HTTP requests to api.orion.riddhimanrana.com.
           * Modify the CameraManager's detection callback to use this new service.
       * Update Data Flow:
           * The app will now send frame data via a POST request to the /v1/frame endpoint.
           * The app no longer needs to wait for a response, simplifying the logic and improving performance and battery life, as it can immediately process the next
             frame.
       * Add Account Management UI:
           * Create a "Profile" or "Settings" tab where users can view their account information and log out
