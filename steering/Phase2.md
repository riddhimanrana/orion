 Phase 2: The Public API Server (`api.orion.riddhimanrana.com`)

  Goal: Replace the local WebSocket server with a scalable, stateless, and secure HTTP API. This decouples the iOS app from the server and eliminates the performance
   issues of the current setup.

   1. Technology Stack:
       * Framework: FastAPI (already in use).
       * Deployment: A container-based hosting service like Render, Fly.io, or AWS/GCP.
       * Asynchronous Task Queue: Redis or RabbitMQ for managing frame processing tasks.
       * Database/Cache: Supabase's built-in Postgres or Redis for storing task results.

   2. Execution Steps:
       * API Refactoring:
           * Transition from WebSocket endpoints to RESTful HTTP endpoints in server/main.py.
           * `POST /v1/frame`: This endpoint will receive the FrameDataMessage from the iOS app. It should be lightweight and fast.
           * `GET /v1/result/{frame_id}`: An endpoint for a client (like the future Mac app) to poll for the processing result of a specific frame.
       * Implement Asynchronous Processing:
           * When the POST /v1/frame endpoint is hit, it will:
               1. Validate the API key (see next step).
               2. Add the frame data to a persistent task queue (e.g., Redis).
               3. Immediately return a 202 Accepted response with a unique task_id.
           * Create a separate Python worker process that listens to the task queue, pulls frame data, and executes the existing process_frame logic.
       * Secure the API:
           * All endpoints must be protected.
           * Clients (iOS/Mac apps) will include their API key (generated in Phase 1) in the Authorization header.
           * The FastAPI backend will validate this key against the api_keys table in Supabase on every request.
       * Store Processing Results:
           * Once the worker finishes processing a frame, it will store the final AnalysisResult in a database or cache (e.g., Postgres or Redis) using the task_id
             as the key.
       * Containerize and Deploy:
           * Create a Dockerfile for the FastAPI application and another for the worker.
           * Use Docker Compose for local development.
           * Deploy the containerized services to a cloud provider and configure the api.orion.riddhimanrana.com domain.
