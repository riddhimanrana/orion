#!/usr/bin/env python3

"""E2E sanity check for the local Orion FastAPI `/ios` WebSocket pipeline.

This script simulates the iOS client:
  - Connects to ws://…/ios
  - (Optionally) sets PROCESSING_MODE to `split`
  - Sends one or more `frame_data` messages with "packet-like" payloads
  - Waits for a ServerResponse + `frame_processed` acknowledgement per frame

Notes:
  - This targets the legacy local Python server under `orion/server/`.
  - In split mode, `image_data` is not required; you can send detections + a VLM description.
  - The server may still run MLX/Gemma on the backend, so allow generous timeouts.

Environment variables:
  ORION_IOS_WS_URL           (default: ws://localhost:8000/ios)
  E2E_FRAME_COUNT            (default: 1)
  E2E_TIMEOUT_S              (default: 90)
  E2E_FORCE_SPLIT_MODE       (default: 1)  # send configuration message
  E2E_INCLUDE_IMAGE_DATA     (default: 0)  # if 1, sends a tiny base64 PNG
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
import uuid

import websockets


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def tiny_png_base64() -> str:
    """Return a 1x1 PNG (opaque black) base64 string."""
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/wcAAgAB/2Wm3n0AAAAASUVORK5CYII="
    )
    return base64.b64encode(png_bytes).decode("ascii")


async def recv_json(ws: websockets.WebSocketClientProtocol, timeout_s: float) -> dict:
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout_s)
    if isinstance(raw, bytes):
        raw = raw.decode("utf8", errors="replace")
    return json.loads(raw)


async def wait_for_message(
    ws: websockets.WebSocketClientProtocol,
    timeout_s: float,
    predicate,
    label: str,
):
    started = time.time()
    while True:
        remaining = max(0.1, timeout_s - (time.time() - started))
        if remaining <= 0:
            raise TimeoutError(f"Timed out waiting for {label}")

        msg = await recv_json(ws, remaining)
        if predicate(msg):
            return msg

        if msg.get("type") == "error":
            raise RuntimeError(
                f"Server error: {msg.get('message', 'unknown')} ({msg.get('details', '')})"
            )


async def main() -> None:
    ws_url = os.environ.get("ORION_IOS_WS_URL", "ws://localhost:8000/ios")
    frame_count = env_int("E2E_FRAME_COUNT", 1)
    timeout_s = env_float("E2E_TIMEOUT_S", 90.0)
    force_split = env_bool("E2E_FORCE_SPLIT_MODE", True)
    include_image = env_bool("E2E_INCLUDE_IMAGE_DATA", False)

    print("E2E: iOS frame pipeline")
    print(f"- WS url: {ws_url}")
    print(f"- Frames: {frame_count}")
    print(f"- Timeout: {timeout_s}s")
    print(f"- Force split mode: {force_split}")
    print(f"- Include image_data: {include_image}")

    async with websockets.connect(ws_url, max_size=16 * 1024 * 1024) as ws:
        ack = await wait_for_message(
            ws,
            timeout_s,
            predicate=lambda m: m.get("type") == "connection_ack",
            label="connection_ack",
        )
        print(f"- Connected: client_id={ack.get('client_id')}")

        if force_split:
            await ws.send(
                json.dumps({"type": "configuration", "processing_mode": "split"})
            )
            await wait_for_message(
                ws,
                timeout_s,
                predicate=lambda m: m.get("type") == "configuration_ack"
                and m.get("processing_mode") == "split",
                label="configuration_ack(split)",
            )
            print("- Server confirmed processing_mode=split")

        device_id = f"e2e-device-{uuid.uuid4()}"
        for i in range(frame_count):
            frame_id = f"e2e-frame-{int(time.time())}-{i}"  # simple, human-friendly
            payload = {
                "type": "frame_data",
                "frame_id": frame_id,
                "timestamp": time.time(),
                "device_id": device_id,
                "vlm_description": f"E2E test frame {i + 1}/{frame_count}",
                "detections": [
                    {
                        "label": "person",
                        "confidence": 0.9,
                        "bbox": [0.1, 0.1, 0.35, 0.6],
                    }
                ],
            }
            if include_image:
                payload["image_data"] = tiny_png_base64()

            await ws.send(json.dumps(payload))
            print(f"- Sent frame_data: frame_id={frame_id}")

            response = await wait_for_message(
                ws,
                timeout_s,
                predicate=lambda m: m.get("frame_id") == frame_id and "analysis" in m,
                label=f"ServerResponse(frame_id={frame_id})",
            )
            scene = (
                response.get("analysis", {})
                .get("scene_description", "")
                .replace("\n", " ")
                .strip()
            )
            print(f"  - ServerResponse OK: scene_description={scene[:120] or '<empty>'}")

            await wait_for_message(
                ws,
                timeout_s,
                predicate=lambda m: m.get("type") == "frame_processed"
                and m.get("frame_id") == frame_id,
                label=f"frame_processed(frame_id={frame_id})",
            )
            print("  - frame_processed OK")

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
