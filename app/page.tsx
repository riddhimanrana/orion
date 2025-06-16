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
          const serverMessage = JSON.parse(event.data as string);
          console.log('Dashboard received message:', serverMessage);

          if (serverMessage.type === 'connection_ack') {
            setSystemLogs(prevLogs => [...prevLogs, {
              id: `log-${Date.now()}-${Math.random()}`, // Add unique ID
              timestamp: new Date().toISOString(),
              level: 'info',
              message: `Connected to dashboard WebSocket. Client ID: ${serverMessage.client_id}`,
            }]);
            return; // Acknowledgment handled
          }
          
          if (serverMessage.type === 'system_message' && serverMessage.event === 'shutdown') {
            setSystemLogs(prevLogs => [...prevLogs, {
              id: `log-${Date.now()}-${Math.random()}`, // Add unique ID
              timestamp: new Date().toISOString(),
              level: 'warn',
              message: `Server is shutting down: ${serverMessage.message}`,
            }]);
            // Optionally, disable UI elements or show a disconnected state
            return;
          }

          if (serverMessage.type === 'live_update') {
            const data = serverMessage; // The server_message itself is the live_update data

            // Add a general log entry for the update
            setSystemLogs(prevLogs => [...prevLogs, {
              id: `log-${data.frame_id}-${Date.now()}`, // Add unique ID
              timestamp: new Date(data.timestamp * 1000).toISOString(), // Server timestamp is in seconds
              level: 'info',
              message: `Live update received for frame: ${data.frame_id}`,
            }]);

            // Video Frame - not sending full image data in this example
            // If you decide to send it from server:
            // if (data.ios_frame_summary.image_data) { // Assuming image_data is added to ios_frame_summary
            //   setVideoFrame(data.ios_frame_summary.image_data);
            // } else {
            //   setVideoFrame(null); // Or a placeholder
            // }
            // For now, let's simulate a new frame coming by just updating a text or something
            // Or, if the iOS app sends frames to a *different* WebSocket that this dashboard also listens to,
            // that would be another way to get live video.
            // For this exercise, we'll assume VideoPlayer might show a static image or status.
            // If `data.vlm_analysis.scene_features` contains an image URL or processed image, use that.
            // For now, no direct update to setVideoFrame from this message.

            // Detections - using vlm_analysis.detections
            if (data.vlm_analysis && data.vlm_analysis.detections) {
              // Ensure the structure matches RawDetection: { label, confidence, bbox, track_id? }
              // The `vlm_analysis.detections` from VisionProcessor._enhance_detection matches this.
              setDetections(data.vlm_analysis.detections as RawDetection[]);
            } else {
              setDetections([]); // Clear if no detections
            }

            // Vision Context Graph - placeholder, needs transformation
            if (data.vlm_analysis && data.vlm_analysis.scene_features) {
              // TODO: Transform scene_features (likely embeddings or relationships) into VisionGraphData
              // For now, just log and clear/reset the graph
              console.log('Scene Features for Vision Graph:', data.vlm_analysis.scene_features);
              setVisionGraph({ nodes: [], edges: [] }); // Reset or update with transformed data
               setSystemLogs(prevLogs => [...prevLogs, {
                id: `log-vlm-${data.frame_id}-${Date.now()}`, // Add unique ID
                timestamp: new Date().toISOString(),
                level: 'debug',
                message: `VLM Scene Features: ${JSON.stringify(data.vlm_analysis.scene_features).substring(0,100)}...`,
              }]);
            }

            // LLM Reasoning Tree
            if (data.llm_reasoning) {
              const llmData = data.llm_reasoning;
              // Construct a simple tree structure for now
              // LLMReasoningNode: { id: string, name: string, children?: LLMReasoningNode[] }
              const reasoningRoot: LLMReasoningNode = {
                id: `llm-${data.frame_id}`,
                name: `Frame: ${data.frame_id}`, // Use 'name' instead of 'label'
                children: [
                  { id: `desc-${data.frame_id}`, name: `Scene: ${llmData.scene_description || 'N/A'}`, value: llmData.scene_description || 'N/A' },
                  ...(llmData.contextual_insights?.map((insight: string, index: number) => ({
                    id: `insight-${data.frame_id}-${index}`,
                    name: `Insight ${index + 1}`, // Use 'name'
                    value: insight,
                  })) || []),
                  // You could add enhanced_detections here too if desired
                  // Example:
                  // ...(llmData.enhanced_detections?.map((det: any, index: number) => ({
                  //  id: `enhanced-det-${data.frame_id}-${index}`,
                  //  name: `Enhanced Det ${index + 1}: ${det.label}`,
                  //  value: `Conf: ${det.confidence}, Context: ${ (det.context || '').substring(0,50)}...`
                  // })) || [])
                ],
              };
              setLlmReasoning(reasoningRoot);
            } else {
              setLlmReasoning(null);
            }
            
            // Log errors from server processing if any
            if (data.final_ios_response_summary && data.final_ios_response_summary.error) {
                setSystemLogs(prevLogs => [...prevLogs, {
                    id: `log-error-${data.frame_id}-${Date.now()}`, // Add unique ID
                    timestamp: new Date().toISOString(),
                    level: 'error',
                    message: `Server processing error for frame ${data.frame_id}: ${data.final_ios_response_summary.error}`,
                }]);
            }


          } else {
            console.warn('Received WebSocket message with unknown type or missing payload:', serverMessage);
             setSystemLogs(prevLogs => [...prevLogs, {
              id: `log-unknown-${Date.now()}-${Math.random()}`, // Add unique ID
              timestamp: new Date().toISOString(),
              level: 'warn',
              message: `Unknown WS message type: ${serverMessage.type || 'N/A'}`,
            }]);
          }

        } catch (error) {
          console.error('Error parsing WebSocket message or handling data:', error);
          setSystemLogs(prevLogs => [...prevLogs, {
            id: `log-client-error-${Date.now()}-${Math.random()}`, // Add unique ID
            timestamp: new Date().toISOString(),
            level: 'error',
            message: `Client-side WS error: ${(error as Error).message}`,
          }]);
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
