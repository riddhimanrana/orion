# Phase 5: Developer Experience and Debugging

**Objective:** Establish a robust set of tools, tests, and workflows to ensure the stability, reliability, and continuous improvement of the entire Orion ecosystem. This phase is crucial for long-term maintainability and efficient development.

---

### 1. Local Development and Simulation

A streamlined local development loop is essential for iterating quickly without needing a physical iOS device.

1.  **Mock Client (`server/tools/mock_client.py`):**
    *   A Python script that simulates the iOS app.
    *   It should accept command-line arguments:
        *   `--api-key`: The API key to use for authentication.
        *   `--image-path`: Path to a single image or a directory of images.
        *   `--mode`: `split` or `full`.
        *   `--api-url`: The URL of the API server (e.g., `http://localhost:8000`).
    *   **Functionality:**
        *   If a directory is provided, it iterates through the images, sending them one by one to the `POST /v1/frame` endpoint with a small delay between each to simulate a video stream.
        *   This allows for end-to-end testing of the entire backend pipeline (API -> Task Queue -> Worker -> DB).

2.  **VS Code Debugging (`.vscode/launch.json`):**
    *   Create a launch configuration to easily debug the FastAPI server.
    ```json
    {
      "version": "0.2.0",
      "configurations": [
        {
          "name": "Python: FastAPI Server",
          "type": "python",
          "request": "launch",
          "module": "uvicorn",
          "args": [
            "main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload"
          ],
          "jinja": true,
          "cwd": "${workspaceFolder}/server",
          "envFile": "${workspaceFolder}/server/.env"
        }
      ]
    }
    ```

---

### 2. Automated Testing Strategy

A comprehensive test suite is critical for preventing regressions.

1.  **Unit Tests (`server/tests/unit/`):**
    *   **Purpose:** Test individual functions in isolation.
    *   **Examples:**
        *   `test_prompt_builder.py`: Write tests for `_build_scene_analysis_prompt` to ensure it correctly handles various combinations of context and detections.
        *   `test_bbox_utils.py`: Test the `get_spatial_label` function with different bounding box coordinates.
        *   `test_security.py`: Test the API key hashing logic.

2.  **Integration Tests (`server/tests/integration/`):**
    *   **Purpose:** Test the interaction between different components of the backend.
    *   **Frameworks:** Use `pytest`, `pytest-asyncio`, and `httpx` for making async requests to the test server.
    *   **Example (`test_api_flow.py`):**
        1.  Use `pytest` fixtures to start the FastAPI application and a mock Redis instance in the background.
        2.  Make a `POST` request to `/v1/frame` with mock data.
        3.  Assert that the response is `202 Accepted` and contains a `task_id`.
        4.  Check the mock Redis queue to ensure the task was enqueued correctly.
        5.  Simulate a worker picking up the task and processing it.
        6.  Assert that the worker stores the result correctly in a test database.

---

### 3. Data Analysis and Model Improvement

The ability to analyze the LLM's performance is key to making Orion smarter.

1.  **Jupyter Environment:**
    *   Add `jupyterlab` and `psycopg2-binary` to a `requirements-dev.txt`.
    *   Create a `notebooks/` directory at the project root.

2.  **Analysis Notebook (`notebooks/result_analysis.ipynb`):**
    *   **Connect to Database:** Write Python code to connect directly to the Supabase PostgreSQL database.
    *   **Fetch Data:** Query the table where analysis results are stored.
    *   **Analyze:**
        *   Use `pandas` to explore the data.
        *   Look for common failure modes: When does the LLM hallucinate? When does it misinterpret the context?
        *   Visualize detection confidence scores and distributions.
    *   **Iterate:** Use the insights from this analysis to refine the prompts sent to the LLM in `llm_processor.py`.

---

### 4. Continuous Integration & Deployment (CI/CD)

Automate testing and deployment to ensure code quality and a reliable release process.

1.  **GitHub Actions Workflow (`.github/workflows/ci.yml`):**
    *   **Trigger:** On every `push` to `main` and on every `pull_request`.
    *   **Jobs:**
        *   **`lint-and-test`:**
            1.  Set up Python environment.
            2.  Install dependencies from `requirements.txt`.
            3.  Run a linter like `ruff` to check for code style issues.
            4.  Run the `pytest` suite (both unit and integration tests). This job should have services for Redis and Postgres for the integration tests.
        *   **`build-and-push-docker` (Optional, but recommended):**
            1.  Triggered only on a `push` to the `main` branch.
            2.  Log in to a container registry (e.g., Docker Hub, GitHub Container Registry).
            3.  Build the Docker images for the API server and the worker.
            4.  Tag the images with the Git commit SHA and `latest`.
            5.  Push the images to the registry.

This structured approach to development and operations will ensure that as Orion grows in complexity, it remains stable, maintainable, and easy to improve.
