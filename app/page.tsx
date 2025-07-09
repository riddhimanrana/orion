"use client"; // Add this directive to mark as a Client Component

import React, { useEffect, useState } from 'react';
import ImageViewer from '@/components/ImageViewer';
import DetectionList from '@/components/DetectionList';
import VisionContextGraph from '@/components/VisionContextGraph';
import LLMReasoningTree from '@/components/LLMReasoningTree';
import LogViewer from '@/components/LogViewer';
import IncomingDataViewer from '@/components/IncomingDataViewer';
import QueueViewer from '@/components/QueueViewer';
import LLMResponseViewer from '@/components/LLMResponseViewer';
import PacketTimeline from '@/components/PacketTimeline';
import RawPacketViewer from '@/components/RawPacketViewer';
import NetworkFlowVisualizer from '@/components/NetworkFlowVisualizer';
import { initWebSocket, closeWebSocket, sendWebSocketMessage } from '@/lib/websocket';

// Import types from component files
import type { Detection as RawDetection } from '@/components/DetectionList'; // Renaming to RawDetection to avoid conflict if needed
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import type { GraphData as VisionGraphData, Node as VisionNode, Edge as VisionEdge } from '@/components/VisionContextGraph'; // Renaming for clarity
import type { LLMReasoningNode } from '@/components/LLMReasoningTree';
import type { LogEntry as SystemLog } from '@/components/LogViewer';

interface PacketEvent {
  event_type: string;
  timestamp: number;
  source: string;
  destination: string;
  summary: string;
  payload: Record<string, unknown>;
} // Import LogEntry and alias as SystemLog

const QueueMonitor: React.FC<{ queueSize: number }> = ({ queueSize }) => (
  <div className="flex items-center">
    <span className="font-medium mr-2">Queue:</span>
    <span className="text-primary-foreground bg-primary px-2 py-1 rounded-full text-xs">
      {queueSize}
    </span>
  </div>
);

// Helper function to safely convert server timestamp to ISO string
const safeTimestampToISO = (timestamp: number): string => {
  try {
    // Convert to milliseconds if it looks like seconds (less than year 2100)
    const tsMs = timestamp < 4102444800 ? timestamp * 1000 : timestamp;
    
    // Ensure timestamp is reasonable (between 1970 and current time + 1 hour)
    const now = Date.now();
    const clampedTs = Math.max(0, Math.min(tsMs, now + 3600000));
    
    const date = new Date(clampedTs);
    
    // Check if date is valid
    if (isNaN(date.getTime())) {
      return new Date().toISOString();
    }
    
    return date.toISOString();
  } catch (error) {
    console.warn('Invalid timestamp:', timestamp, error);
    return new Date().toISOString();
  }
};

export default function Home() {
  const [detections, setDetections] = useState<RawDetection[]>([]);
  const [visionGraph, setVisionGraph] = useState<VisionGraphData>({ nodes: [], edges: [] });
  const [llmReasoning, setLlmReasoning] = useState<LLMReasoningNode | null>(null);
  const [systemLogs, setSystemLogs] = useState<SystemLog[]>([]);
  const [videoFrame, setVideoFrame] = useState<string | null>(null); // e.g., base64 string for video
  const [packetEvents, setPacketEvents] = useState<PacketEvent[]>([]);
  const [selectedPacketEvent, setSelectedPacketEvent] = useState<PacketEvent | null>(null);
  const [processingMode, setProcessingMode] = useState<string>('split'); // Default to split
  const [modelHealth, setModelHealth] = useState<Record<string, boolean>>({});
  const [lastEvent, setLastEvent] = useState<string | null>(null);
  const [queueSize, setQueueSize] = useState<number>(0);
  const [llmProcessingStats, setLlmProcessingStats] = useState<any>(null);
  const [visionProcessingStats, setVisionProcessingStats] = useState<any>(null);
  const [incomingData, setIncomingData] = useState<any>(null);
  const [queueContents, setQueueContents] = useState<any[]>([]);
  const [llmSceneDescription, setLlmSceneDescription] = useState<string | null>(null);

  useEffect(() => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const ws = initWebSocket({
      onOpen: () => {
        console.log('Dashboard WebSocket connected.');
        // Request current processing mode from server
        sendWebSocketMessage(JSON.stringify({ type: 'request_config' }));
      },
      onMessage: (event) => {
        try {
          const serverMessage = JSON.parse(event.data as string);
          console.log('Dashboard received message:', serverMessage);

          if (serverMessage.type === 'connection_ack') {
            setSystemLogs(prevLogs => [...prevLogs, {
              id: `log-${crypto.randomUUID()}`,
              timestamp: new Date().toISOString(),
              level: 'info',
              message: `Connected to dashboard WebSocket. Client ID: ${serverMessage.client_id}`,
            }]);
            return; // Acknowledgment handled
          }

          if (serverMessage.type === 'server_config') {
            setProcessingMode(serverMessage.processing_mode);
            setSystemLogs(prevLogs => [...prevLogs, {
              id: `log-${crypto.randomUUID()}`,
              timestamp: new Date().toISOString(),
              level: 'info',
              message: `Server config received. Mode: ${serverMessage.processing_mode}`,
            }]);
            return; // Config handled
          }
          
          if (serverMessage.type === 'system_message' && serverMessage.event === 'shutdown') {
            setSystemLogs(prevLogs => [...prevLogs, {
              id: `log-${crypto.randomUUID()}`,
              timestamp: new Date().toISOString(),
              level: 'warn',
              message: `Server is shutting down: ${serverMessage.message}`,
            }]);
            // Optionally, disable UI elements or show a disconnected state
            return;
          }

          // Handle queue updates
          if (serverMessage.type === 'frame_enqueued') {
            setQueueSize(serverMessage.data.queue_size);
            setQueueContents(serverMessage.data.queue_contents || []);
            setSystemLogs(prevLogs => [...prevLogs, {
              id: `log-enqueue-${serverMessage.data.frame_id}-${crypto.randomUUID()}`,
              timestamp: new Date().toISOString(),
              level: 'info',
              message: `Frame ${serverMessage.data.frame_id} enqueued. Queue size: ${serverMessage.data.queue_size}`,
            }]);
            return; // Event handled
          }

          if (serverMessage.type === 'frame_processing_started') {
            setQueueSize(serverMessage.data.queue_size);
            setQueueContents(serverMessage.data.queue_contents || []);
            setSystemLogs(prevLogs => [...prevLogs, {
              id: `log-proc-start-${serverMessage.data.frame_id}-${crypto.randomUUID()}`,
              timestamp: new Date().toISOString(),
              level: 'info',
              message: `Processing started for frame ${serverMessage.data.frame_id}. Queue size: ${serverMessage.data.queue_size}`,
            }]);
            return; // Event handled
          }

          if (serverMessage.type === 'frame_processed_successfully') {
            setQueueSize(serverMessage.data.queue_size);
            setQueueContents(serverMessage.data.queue_contents || []);
            setSystemLogs(prevLogs => [...prevLogs, {
              id: `log-proc-success-${serverMessage.data.frame_id}-${crypto.randomUUID()}`,
              timestamp: new Date().toISOString(),
              level: 'info',
              message: `Frame ${serverMessage.data.frame_id} processed successfully. Queue size: ${serverMessage.data.queue_size}`,
            }]);
            return; // Event handled
          }

          if (serverMessage.type === 'live_update') {
            setLastEvent(serverMessage.event);
            const data = serverMessage.data;

            // Add a general log entry for the update
            setSystemLogs(prevLogs => [...prevLogs, {
              id: `log-${data.frame_id}-${crypto.randomUUID()}`, // Ensure unique ID
              timestamp: safeTimestampToISO(data.timestamp),
              level: 'info',
              message: `Live update received for frame: ${data.frame_id}`,
            }]);

            // Video Frame - now sending image_data if available
            if (data.vlm_analysis && data.vlm_analysis.ios_frame_summary && data.vlm_analysis.ios_frame_summary.image_data) {
              setVideoFrame(data.vlm_analysis.ios_frame_summary.image_data);
              console.log('Received image data:', data.vlm_analysis.ios_frame_summary.image_data ? 'Present' : 'Not Present');
            } else {
              setVideoFrame(null); // Clear or a placeholder if no image data
              console.log('No image data received for this frame.');
            }

            // Detections - using vlm_analysis.detections
            if (data.vlm_analysis && data.vlm_analysis.detections) {
              // Ensure the structure matches RawDetection: { label, confidence, bbox, track_id? }
              // The `vlm_analysis.detections` from VisionProcessor._enhance_detection matches this.
              setDetections(data.vlm_analysis.detections as RawDetection[]);
              console.log('Received detections:', data.vlm_analysis.detections);
            } else {
              setDetections([]); // Clear if no detections
              console.log('No detections received for this frame.');
            }

            // Vision Context Graph - placeholder, needs transformation
            if (data.vlm_analysis && data.vlm_analysis.scene_features) {
              // TODO: Transform scene_features (likely embeddings or relationships) into VisionGraphData
              // For now, just log and clear/reset the graph
              console.log('Scene Features for Vision Graph:', data.vlm_analysis.scene_features);
              setVisionGraph({ nodes: [], edges: [] }); // Reset or update with transformed data
               setSystemLogs(prevLogs => [...prevLogs, {
                id: `log-vlm-${data.frame_id}-${crypto.randomUUID()}`,
                timestamp: new Date().toISOString(),
                level: 'debug',
                message: `VLM Scene Features: ${JSON.stringify(data.vlm_analysis.scene_features).substring(0,100)}...`,
              }]);
            }

            // LLM Reasoning Tree
            if (data.llm_reasoning) {
              const llmData = data.llm_reasoning;
              // Set the clean LLM scene description for the dedicated viewer
              setLlmSceneDescription(llmData.scene_description || null);

              // Construct a simple tree structure for the LLM Reasoning Tree component
              const reasoningRoot: LLMReasoningNode = {
                id: `llm-${data.frame_id}-${crypto.randomUUID()}`,
                name: `Frame: ${data.frame_id}`,
                children: [
                  { id: `desc-${data.frame_id}-${crypto.randomUUID()}`, name: `Scene: ${llmData.scene_description || 'N/A'}`, value: llmData.scene_description || 'N/A' },
                  ...(llmData.contextual_insights?.map((insight: string, index: number) => ({
                    id: `insight-${data.frame_id}-${index}-${crypto.randomUUID()}`,
                    name: `Insight ${index + 1}`,
                    value: insight,
                  })) || []),
                ],
              };
              setLlmReasoning(reasoningRoot);
              console.log('Received LLM reasoning:', data.llm_reasoning);
            } else {
              setLlmReasoning(null);
              setLlmSceneDescription(null);
              console.log('No LLM reasoning received for this frame.');
            }

            // Pass historical context to LLMReasoningTree
            if (data.context) {
              setLlmReasoning(prev => ({
                ...(prev || { id: `llm-root-${crypto.randomUUID()}`, name: "LLM Reasoning" }),
                historicalContext: data.context,
              }));
            }
            
            // Log errors from server processing if any
            if (data.final_ios_response_summary && data.final_ios_response_summary.error) {
                setSystemLogs(prevLogs => [...prevLogs, {
                    id: `log-error-${data.frame_id}-${crypto.randomUUID()}`,
                    timestamp: new Date().toISOString(),
                    level: 'error',
                    message: `Server processing error for frame ${data.frame_id}: ${data.final_ios_response_summary.error}`,
                }]);
            }

            // Handle packet events
            if (data.packet_events && Array.isArray(data.packet_events)) {
              setPacketEvents(prevEvents => [...prevEvents, ...data.packet_events]);
              console.log('Received packet events:', data.packet_events);
            } else {
              console.log('No packet events received for this frame.');
            }

            // Update server status (processing mode and model health)
            if (data.server_status) {
              setProcessingMode(data.server_status.processing_mode);
              setModelHealth(data.server_status.model_health);
              setQueueSize(data.server_status.queue_size || 0);
              setLlmProcessingStats(data.server_status.llm_processing_stats || null);
              setVisionProcessingStats(data.server_status.vision_processing_stats || null);
            }

            setIncomingData(data);


          } else {
            console.warn('Received WebSocket message with unknown type or missing payload:', serverMessage);
             setSystemLogs(prevLogs => [...prevLogs, {
              id: `log-unknown-${crypto.randomUUID()}`,
              timestamp: new Date().toISOString(),
              level: 'warn',
              message: `Unknown WS message type: ${serverMessage.type || 'N/A'}`,
            }]);
          }

        } catch (error) {
          console.error('Error parsing WebSocket message or handling data:', error);
          setSystemLogs(prevLogs => [...prevLogs, {
            id: `log-client-error-${crypto.randomUUID()}`,
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
        <div className="ml-auto flex items-center space-x-4 text-sm">
          <div className="flex items-center">
            <span className="font-medium mr-2">Mode:</span>
            <span className="text-primary-foreground bg-primary px-2 py-1 rounded-full text-xs">
              {processingMode.toUpperCase()}
            </span>
          </div>
          <QueueMonitor queueSize={queueSize} />
          <div className="flex items-center space-x-2">
            <span className="font-medium">Models:</span>
            {Object.entries(modelHealth).map(([modelName, isHealthy]) => (
              <span
                key={modelName}
                className={`px-2 py-1 rounded-full text-xs ${isHealthy ? 'bg-green-500 text-white' : 'bg-red-500 text-white'}`}>
                {modelName.toUpperCase()}: {isHealthy ? 'Healthy' : 'Unhealthy'}
              </span>
            ))}
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Left Panel: Packet Timeline & Raw Data Viewer */}
        <aside className="w-1/3 min-w-[300px] max-w-[500px] bg-card border-r p-4 flex flex-col gap-4 overflow-y-auto">
          <div className="flex-1 min-h-[300px]">
            <PacketTimeline
              packetEvents={packetEvents}
              onSelectPacket={setSelectedPacketEvent}
              selectedPacket={selectedPacketEvent}
            />
          </div>
          <div className="flex-1 min-h-[300px]">
            <RawPacketViewer packet={selectedPacketEvent} />
          </div>
        </aside>

        {/* Center Panel: Video, Detections, Vision Graph */}
        <section className="flex-1 bg-background p-4 flex flex-col gap-4 overflow-y-auto">
          <div className="w-full mb-4">
            <NetworkFlowVisualizer
              lastEvent={lastEvent}
              processingMode={processingMode}
              llmProcessingStats={llmProcessingStats}
              visionProcessingStats={visionProcessingStats}
              queueSize={queueSize}
            />
          </div>
          <div className="flex-1 min-h-[300px] flex items-center justify-center">
            <div className="w-full h-full max-w-4xl max-h-[70vh]">
              <ImageViewer frameData={videoFrame} />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 flex-1 min-h-[300px]">
            <div className="flex-1">
              <DetectionList detections={detections} />
            </div>
            <div className="flex-1">
              <VisionContextGraph graphData={visionGraph} />
            </div>
          </div>
        </section>

        {/* Right Panel: LLM Reasoning & Logs */}
        <aside className="w-1/3 min-w-[300px] max-w-[500px] bg-card border-l p-4 flex flex-col gap-4 overflow-y-auto">
          <div className="flex-1 min-h-[150px]">
            <LLMResponseViewer response={llmSceneDescription} />
          </div>
          <div className="flex-1 min-h-[300px]">
            <LLMReasoningTree reasoningData={llmReasoning} historicalContext={llmReasoning?.historicalContext} />
          </div>
          <div className="flex-1 min-h-[300px]">
            <QueueViewer queueSize={queueSize} queueContents={queueContents} />
          </div>
          <div className="flex-1 min-h-[300px]">
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
