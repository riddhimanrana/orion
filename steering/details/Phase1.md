# Phase 1: Website, Authentication, and User Dashboard

**Objective:** Establish the public-facing identity of Orion at `orion.riddhimanrana.com`. This phase focuses on creating the user-facing website, implementing a robust authentication system using Supabase, and building a dashboard for users to manage their API keys. This is the foundational step that decouples the system from a local-only setup and prepares for a multi-user, multi-device architecture.

---

### 1. Technology Stack

*   **Framework:** Next.js with TypeScript
*   **Styling:** Tailwind CSS
*   **Backend & Auth:** Supabase (PostgreSQL, Authentication, Storage)
*   **Deployment:** Vercel

---

### 2. Directory Structure

All work for this phase will be done inside the `orion/website/` directory.

```
website/
├── components/
│   ├── auth/
│   │   ├── AuthForm.tsx
│   │   └── UserProfile.tsx
│   ├── dashboard/
│   │   ├── ApiKeyManager.tsx
│   │   └── UsageMonitor.tsx
│   └── layout/
│       ├── Navbar.tsx
│       └── Footer.tsx
├── lib/
│   ├── supabaseClient.ts   # Client-side Supabase helper
│   └── supabaseAdmin.ts    # Server-side Supabase admin client (for API key management)
├── pages/
│   ├── api/
│   │   └── auth/
│   │       └── [..supabase].ts # Auth callbacks
│   ├── auth/
│   │   ├── login.tsx
│   │   └── signup.tsx
│   ├── dashboard.tsx       # Protected route
│   └── index.tsx           # Landing page
├── public/
│   └── orion-logo.svg
├── styles/
│   └── globals.css
├── tailwind.config.js
├── tsconfig.json
└── package.json
```

---

### 3. Supabase Project Setup

1.  **Create Project:**
    *   Go to [supabase.com](https://supabase.com) and create a new project named `orion`.
    *   Save the **Project URL** and **`anon` public key**. These will be your environment variables.

2.  **Configure Authentication:**
    *   Navigate to `Authentication -> Providers`.
    *   Enable **Email**, **Google**, and **Apple**. Follow the Supabase guides to get the necessary credentials for Google and Apple.
    *   Go to `Authentication -> URL Configuration` and set your site URL to `http://localhost:3000` for development and `https://orion.riddhimanrana.com` for production.

3.  **Database Schema:**
    *   Navigate to the `SQL Editor` and run the following queries to create the necessary tables.

    ```sql
    -- Table to link devices to users
    CREATE TABLE devices (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
        device_type TEXT NOT NULL, -- 'ios' or 'macos'
        device_name TEXT,
        created_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()) NOT NULL,
        last_seen_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()) NOT NULL
    );

    -- Table to store hashed API keys for users
    CREATE TABLE api_keys (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
        key_name TEXT NOT NULL,
        key_hash TEXT NOT NULL UNIQUE,
        created_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()) NOT NULL,
        last_used_at TIMESTAMPTZ
    );

    -- Enable Row Level Security (RLS) for the new tables
    ALTER TABLE devices ENABLE ROW LEVEL SECURITY;
    ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;

    -- Policies: Users can only manage their own devices and API keys
    CREATE POLICY "Allow individual user access to own devices"
    ON devices FOR ALL
    USING (auth.uid() = user_id);

    CREATE POLICY "Allow individual user access to own API keys"
    ON api_keys FOR ALL
    USING (auth.uid() = user_id);
    ```

---

### 4. Next.js Project Implementation

1.  **Initialize Project:**
    *   In the `orion/` directory, run: `npx create-next-app@latest website --typescript --tailwind --eslint`
    *   Install Supabase helpers: `npm install @supabase/auth-helpers-nextjs @supabase/supabase-js`

2.  **Environment Variables:**
    *   Create a `.env.local` file in the `website/` directory:
        ```
        NEXT_PUBLIC_SUPABASE_URL=YOUR_SUPABASE_PROJECT_URL
        NEXT_PUBLIC_SUPABASE_ANON_KEY=YOUR_SUPABASE_ANON_KEY
        SUPABASE_SERVICE_ROLE_KEY=YOUR_SUPABASE_SERVICE_ROLE_KEY
        ```

3.  **Landing Page (`pages/index.tsx`):**
    *   **Hero Section:** A large, impactful title ("Orion: See Beyond the Now"), a brief tagline, and a call-to-action (CTA) button ("Sign Up for Free").
    *   **Features Section:** Use cards to highlight key features: Real-time Analysis, Temporal Context, On-Device & Server Modes, Privacy-Focused.
    *   **How It Works:** A visual diagram showing the flow from iOS -> API -> Mac Server -> Analysis.
    *   **Technology Stack:** Display logos of key technologies (Swift, Python, MLX, Next.js, Supabase).

4.  **Authentication (`pages/auth/`):**
    *   Use the `@supabase/auth-helpers-nextjs` library to create a Supabase client instance in `lib/supabaseClient.ts`.
    *   Build the `AuthForm.tsx` component to handle both login and signup. Use the `supabaseClient.auth.signInWithPassword()` and `supabaseClient.auth.signUp()` methods.
    *   Implement "Sign in with Google" and "Sign in with Apple" buttons using `supabaseClient.auth.signInWithOAuth()`.

5.  **Dashboard (`pages/dashboard.tsx`):**
    *   This page must be a protected route. Use Supabase's server-side helpers (`createServerComponentClient`) in the page's `getServerSideProps` function to check for a valid session and redirect if the user is not authenticated.
    *   **API Key Manager (`components/dashboard/ApiKeyManager.tsx`):**
        *   **UI:** A button to "Generate New API Key", a list of existing keys (showing only the name and creation date, not the key itself), and a "Revoke" button for each.
        *   **Logic:**
            1.  When the user clicks "Generate", call a new Next.js API route (e.g., `pages/api/keys/create.ts`).
            2.  The API route will generate a secure random string for the API key and a hash of that key.
            3.  **Store the hash** in the `api_keys` table in Supabase.
            4.  **Return the raw, unhashed key to the user ONCE.** Display it in a modal with a "Copy" button and a warning that it will not be shown again.

---

### 5. Deployment

1.  **Push to GitHub:** Ensure the `orion/website` directory is part of your `riddhimanrana/orion` repository.
2.  **Vercel Project:**
    *   Create a new project on Vercel and link it to your GitHub repository.
    *   Set the **Root Directory** to `website`.
    *   Vercel will automatically detect it's a Next.js project.
3.  **Environment Variables:**
    *   In the Vercel project settings, add the same environment variables from your `.env.local` file.
4.  **Domain:**
    *   In the Vercel project settings, go to `Domains` and add `orion.riddhimanrana.com`. Follow the instructions to update your DNS records.
5.  **Deploy:** Trigger a deployment. Vercel will build and deploy the site.
