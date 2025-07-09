import React, { useState, useEffect } from 'react';
import { Phone, Server, Globe, ArrowRight } from 'lucide-react';

interface LLMProcessingStats {
  scenes_analyzed: number;
  average_confidence: number;
  questions_answered: number;
}

interface VisionProcessingStats {
  frames_processed: number;
  total_detections: number;
  average_confidence: number;
  average_detections_per_frame: number;
}

interface NetworkFlowVisualizerProps {
  lastEvent: string | null; // e.g., 'ios_frame_received', 'vlm_analysis_complete', etc.
  processingMode: string;
  llmProcessingStats: LLMProcessingStats | null;
  visionProcessingStats: VisionProcessingStats | null;
  queueSize: number; // Add queueSize prop
}

const NetworkFlowVisualizer: React.FC<NetworkFlowVisualizerProps> = ({
  lastEvent,
  processingMode,
  llmProcessingStats,
  visionProcessingStats,
  queueSize,
}) => {
  const [activeSegment, setActiveSegment] = useState<string | null>(null);
  const [currentProcessingStage, setCurrentProcessingStage] = useState<string | null>(null);

  useEffect(() => {
    if (lastEvent) {
      let segment = null;
      let stage = null;
      switch (lastEvent) {
        case 'ios_frame_received':
          segment = 'mobile-to-server';
          stage = 'Frame Received';
          break;
        case 'yolo_analysis_complete':
          segment = 'server-processing';
          stage = 'YOLO Analysis';
          break;
        case 'vlm_analysis_complete':
          segment = 'server-processing';
          stage = 'VLM Analysis';
          break;
        case 'llm_reasoning_complete':
          segment = 'server-processing';
          stage = 'LLM Reasoning';
          break;
        case 'response_sent_to_ios':
          segment = 'server-to-dashboard';
          stage = 'Response Sent';
          break;
        case 'live_update':
          segment = 'server-to-dashboard';
          stage = 'Dashboard Update';
          break;
        default:
          segment = null;
          stage = null;
      }
      setActiveSegment(segment);
      setCurrentProcessingStage(stage);

      const timer = setTimeout(() => setActiveSegment(null), 1000);
      return () => clearTimeout(timer);
    }
  }, [lastEvent]);

  const getSegmentClasses = (segmentName: string) => {
    return `transition-all duration-500 ${activeSegment === segmentName ? 'text-green-400 scale-110' : 'text-muted-foreground'}`;
  };

  return (
    <div className="w-full p-4 border rounded-md bg-card flex flex-col items-center justify-center gap-4">
      <h2 className="text-lg font-semibold">Network Flow Overview</h2>
      <div className="flex items-center justify-around w-full max-w-2xl">
        {/* Mobile Icon */}
        <div className={`flex flex-col items-center p-2 rounded-lg ${getSegmentClasses('mobile-to-server')}`}>
          <Phone className="h-10 w-10" />
          <span className="text-sm mt-1">Mobile</span>
        </div>

        {/* Arrow to Server */}
        <div className={`flex flex-col items-center ${getSegmentClasses('mobile-to-server')}`}>
          <ArrowRight className="h-8 w-8" />
          <span className="text-xs">Data Stream</span>
        </div>

        {/* Server Icon */}
        <div className={`flex flex-col items-center p-2 rounded-lg ${getSegmentClasses('server-processing')}`}>
          <Server className="h-10 w-10" />
          <span className="text-sm mt-1">Server</span>
        </div>

        {/* Arrow to Web (Dashboard) */}
        <div className={`flex flex-col items-center ${getSegmentClasses('server-to-dashboard')}`}>
          <ArrowRight className="h-8 w-8" />
          <span className="text-xs">Live Updates</span>
        </div>

        {/* Web Icon */}
        <div className={`flex flex-col items-center p-2 rounded-lg ${getSegmentClasses('server-to-dashboard')}`}>
          <Globe className="h-10 w-10" />
          <span className="text-sm mt-1">Dashboard</span>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4 w-full max-w-2xl text-sm text-muted-foreground mt-2">
        <p><strong>Mode:</strong> {processingMode.toUpperCase()}</p>
          <p><strong>Queue Size:</strong> {queueSize}</p>
        <p><strong>Current Stage:</strong> {currentProcessingStage || 'Awaiting data...'}</p>
        {llmProcessingStats && (
          <>
            <p><strong>LLM Scenes:</strong> {llmProcessingStats.scenes_analyzed}</p>
            <p><strong>LLM Avg Conf:</strong> {(llmProcessingStats.average_confidence * 100).toFixed(1)}%</p>
            <p><strong>LLM Q&A:</strong> {llmProcessingStats.questions_answered}</p>
          </>
        )}
        {visionProcessingStats && (
          <>
            <p><strong>Vision Frames:</strong> {visionProcessingStats.frames_processed}</p>
            <p><strong>Vision Detections:</strong> {visionProcessingStats.total_detections}</p>
            <p><strong>Vision Avg Conf:</strong> {(visionProcessingStats.average_confidence * 100).toFixed(1)}%</p>
          </>
        )}
      </div>
      <p className="text-sm text-muted-foreground text-center mt-2">
        {lastEvent ? `Last Event: ${lastEvent.replace(/_/g, ' ')}` : 'Awaiting data...'}
      </p>
    </div>
  );
};

export default NetworkFlowVisualizer;
