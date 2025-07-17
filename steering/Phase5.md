 Phase 5: Developer Experience and Debugging

  Goal: Build robust tools and processes to make iterating on the core ML and server logic faster and more reliable.

   1. Execution Steps:
       * Enhanced Local Development:
           * Create a suite of scripts to simulate the entire data flow without needing a physical iOS device.
           * A "mock client" script could send a directory of images to the /v1/frame endpoint to test the full pipeline.
           * Configure launch.json for VS Code to allow for easy debugging of the FastAPI server with breakpoints.
       * Testing Framework:
           * Expand on the existing pytest.ini setup.
           * Write unit tests for individual functions (e.g., prompt generation, bounding box calculations).
           * Write integration tests that call the API endpoints and verify that tasks are correctly created, processed by the worker, and results are stored. Use
             pytest-asyncio for testing async code.
       * Data Analysis & Model Improvement:
           * Create Jupyter notebooks to connect to the results database.
           * Analyze the stored AnalysisResult data to debug the LLM's reasoning and the temporal context creation. This is crucial for improving the "intelligence"
             of the system.
       * Continuous Integration/Continuous Deployment (CI/CD):
           * Set up a GitHub Actions workflow that automatically runs all tests on every pull request.
           * Add a workflow to automatically build and push the API server's Docker container to a registry (e.g., Docker Hub, GitHub Container Registry) upon
             merging to the main branch.
