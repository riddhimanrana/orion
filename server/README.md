# Orion Backend Server (Legacy)

This is an older prototype version of the Orion server component. It powered real-time communication via a WebSocket connection on a local Mac-only FastAPI backend.

I'm currently working on a new cloud API server system and a dedicated macOS server application. This legacy code can be explored for reference, but detailed documentation and deployment instructions will be provided with the upcoming Python FastAPI backend that will power both the Mac app and the cloud deployment.

## Requirements

- Python 3.10 or later  
- macOS 12.0 or later  
- FastAPI  
- Uvicorn  
- MLX  
- PyTorch (Apple Silicon optimized)  

## Frameworks

- FastAPI for the web server  
- WebSockets for real-time streaming  
- MLX for model inference  
- Uvicorn for ASGI serving  

## Getting Started

1. Clone the repository:

   ```bash
   git clone https://github.com/riddhimanrana/orion.git
   cd orion/server
   ```

2. Install dependencies:  

   ```bash
   pip install -r requirements.txt
   ```

3. Start the server:  

   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

## Legacy Prototype Details

- WebSocket endpoint for iOS clients: `/ws/ios/{client_id}`  
- Dashboard WebSocket endpoint: `/ws/dashboard`  
- Frame queue processing with LLM and vision processors  
- Designed for local development on a Mac only  

Feel free to explore the code base. Full architecture and deployment instructions for the upcoming cloud and macOS server versions will be shared soon.
