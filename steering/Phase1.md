Phase 1: Website, Authentication, and User Dashboard

  Goal: Establish the public-facing presence of Orion. Create the foundation for user accounts, which will link the iOS and macOS apps together.

   1. Technology Stack:
       * Framework: Next.js (reusing existing frontend expertise).
       * Styling: Tailwind CSS (already in use).
       * Backend-as-a-Service (BaaS): Supabase for authentication, user management, and database.

   2. Execution Steps:
       * Supabase Project Setup:
           * Create a new project in Supabase.
           * Enable and configure authentication providers: Email/Password, Google, and Apple.
           * Define the initial database schema:
               * users: (Handled by Supabase Auth).
               * devices: To link a user's account to their specific iOS and macOS app instances. Columns: id, user_id, device_type (e.g., 'ios', 'macos'),
                 device_name, created_at.
               * api_keys: To allow apps to authenticate with the backend API. Columns: id, user_id, key_hash, created_at, last_used_at.
       * Website Development (`orion.riddhimanrana.com`):
           * Initialize a new Next.js project.
           * Landing Page: Design and build a modern, compelling landing page that explains what Orion is, its core features (real-time analysis, temporal context),
             and shows the system architecture.
           * Authentication UI:
               * Create pages for Signup, Login, and Password Reset.
               * Integrate the Supabase Auth UI or build custom forms using the @supabase/auth-helpers-nextjs library for a seamless experience.
       * User Dashboard:
           * Create a new protected route (e.g., /dashboard) accessible only to logged-in users.
           * API Key Management: Build a UI where users can generate, view, and revoke API keys for their devices. This is critical for connecting the apps in later
             phases.
           * Usage Monitoring: Design a section to display usage statistics. Initially, this can be a placeholder.
       * Deployment:
           * Deploy the Next.js application to a platform like Vercel.
           * Configure the orion.riddhimanrana.com custom domain.
