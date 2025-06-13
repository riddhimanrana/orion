"use client"; // Add this directive to mark as a Client Component

// eslint-disable-next-line @typescript-eslint/no-unused-vars
import React, { useEffect, useState } from 'react';
import VideoPlayer from '@/components/VideoPlayer';
import DetectionList from '@/components/DetectionList';
import VisionContextGraph from '@/components/VisionContextGraph';
import LLMReasoningTree from '@/components/LLMReasoningTree';
import LogViewer from '@/components/LogViewer';
import { initWebSocket, closeWebSocket } from '@/lib/websocket';

// Import types from component files
import type { Detection as RawDetection } from '@/components/DetectionList'; // Renaming to RawDetection to avoid conflict if needed
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import type { GraphData as VisionGraphData, Node as VisionNode, Edge as VisionEdge } from '@/components/VisionContextGraph'; // Renaming for clarity
import type { LLMReasoningNode } from '@/components/LLMReasoningTree';
import type { LogEntry as SystemLog } from '@/components/LogViewer'; // Import LogEntry and alias as SystemLog


export default function Home() {
  const [detections, setDetections] = useState<RawDetection[]>([]);
  const [visionGraph, setVisionGraph] = useState<VisionGraphData>({ nodes: [], edges: [] });
  const [llmReasoning, setLlmReasoning] = useState<LLMReasoningNode | null>(null);
  const [systemLogs, setSystemLogs] = useState<SystemLog[]>([]);
  const [videoFrame, setVideoFrame] = useState<string | null>(null); // e.g., base64 string for video

  useEffect(() => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const ws = initWebSocket({
      onOpen: () => {
        console.log('Dashboard WebSocket connected.');
        // Potentially send an initial message if required by the server
      },
      onMessage: (event) => {
        try {
          const message = JSON.parse(event.data as string);
          console.log('Parsed WebSocket message:', message);

          // Basic message routing based on a 'type' field in the message
          // The Python server will need to send messages in this format:
          // { "type": "video_frame", "payload": "base64_string..." }
          // { "type": "detections", "payload": [{...}, {...}] }
          // etc.

          if (message.type === 'video_frame' && message.payload) {
            setVideoFrame(message.payload as string);
          } else if (message.type === 'detections' && message.payload) {
            // Assuming payload is an array of detections.
            // Decide if you want to append or replace. For now, let's append.
            setDetections(prevDetections => [...prevDetections, ...(message.payload as RawDetection[])]);
          } else if (message.type === 'vision_context_graph' && message.payload) {
            setVisionGraph(message.payload as VisionGraphData);
          } else if (message.type === 'llm_reasoning' && message.payload) {
            setLlmReasoning(message.payload as LLMReasoningNode);
          } else if (message.type === 'system_log' && message.payload) {
            setSystemLogs(prevLogs => [...prevLogs, message.payload as SystemLog]);
          } else {
            console.warn('Received WebSocket message with unknown type or missing payload:', message);
          }

        } catch (error) {
          console.error('Error parsing WebSocket message or handling data:', error);
        }
      },
      onError: (error) => {
        console.error('Dashboard WebSocket error:', error);
      },
      onClose: (event) => {
        console.log('Dashboard WebSocket disconnected:', event.reason);
      },
    });

    // Cleanup on component unmount
    return () => {
      closeWebSocket();
    };
  }, []); // Empty dependency array ensures this runs only once on mount

  return (
    <main className="flex flex-col h-screen bg-background text-foreground font-[family-name:var(--font-geist-sans)]">
      <header className="h-16 border-b border-border bg-card flex items-center px-6 shrink-0">
        {/* Icon Placeholder - Replace with your actual icon component or <img> tag */}
        <svg
          className="h-8 w-8 mr-3 text-primary" // Example styling
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth="2"
        >
          <circle cx="12" cy="12" r="10" />
          {/* You can put a letter or a simple shape inside the circle if you like */}
          {/* e.g., <text x="12" y="16" textAnchor="middle" fontSize="12" fill="white">O</text> */}
        </svg>
        <h1 className="text-xl font-semibold text-foreground">Orion Vision Dashboard</h1>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar */}
        <aside className="w-1/4 min-w-[300px] max-w-[400px] bg-card border-r p-4 flex flex-col gap-4 overflow-y-auto">
          <div className="flex-1 min-h-[300px]"> {/* Ensure minimum height for visibility */}
            <DetectionList detections={detections} />
          </div>
          <div className="flex-1 min-h-[300px]"> {/* Ensure minimum height for visibility */}
            <VisionContextGraph graphData={visionGraph} />
          </div>
        </aside>

        {/* Main Content Area */}
        <section className="flex-1 bg-background p-4 flex items-center justify-center">
          <div className="w-full h-full max-w-4xl max-h-[70vh]"> {/* Constrain video player size */}
            <VideoPlayer frameData={videoFrame} />
          </div>
        </section>

        {/* Right Sidebar */}
        <aside className="w-1/4 min-w-[300px] max-w-[400px] bg-card border-l p-4 flex flex-col gap-4 overflow-y-auto">
          <div className="flex-1 min-h-[300px]"> {/* Ensure minimum height for visibility */}
            <LLMReasoningTree reasoningData={llmReasoning} />
          </div>
          <div className="flex-1 min-h-[300px]"> {/* Ensure minimum height for visibility */}
            <LogViewer logs={systemLogs} />
          </div>
        </aside>
      </div>

      {/* Footer (Optional - can be added later) */}
      {/* <footer className="h-10 bg-card border-t p-2 flex items-center justify-center text-sm text-muted-foreground">
        <p>&copy; {new Date().getFullYear()} Vision Dashboard</p>
      </footer> */}
    </main>
  );
}
