import React, { useState, useEffect } from 'react';
import { Phone, Server, Globe, ArrowRight, Hourglass } from 'lucide-react';

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
  lastEvent: string | null;
  processingMode: string;
  llmProcessingStats: LLMProcessingStats | null;
  visionProcessingStats: VisionProcessingStats | null;
  queueSize: number;
}

const NetworkFlowVisualizer: React.FC<NetworkFlowVisualizerProps> = ({
  lastEvent,
  processingMode,
  llmProcessingStats,
  visionProcessingStats,
  queueSize,
}) => {
  const [activeSegment, setActiveSegment] = useState<string | null>(null);
  const [isWaiting, setIsWaiting] = useState(false);

  useEffect(() => {
    let segment: string | null = null;
    let waiting = false;

    switch (lastEvent) {
      case 'ios_frame_received':
        segment = 'mobile-to-server';
        if (processingMode === 'full') waiting = true;
        break;
      case 'frame_enqueued':
        segment = 'server-queue';
        break;
      case 'frame_processing_started':
        segment = 'server-processing';
        break;
      case 'response_sent_to_ios':
        segment = 'server-to-mobile';
        waiting = false;
        break;
      case 'live_update':
        segment = 'server-to-dashboard';
        break;
      default:
        break;
    }

    setActiveSegment(segment);
    setIsWaiting(waiting);

    if (segment) {
      const timer = setTimeout(() => setActiveSegment(null), 1000);
      return () => clearTimeout(timer);
    }
  }, [lastEvent, processingMode]);

  const getSegmentClasses = (segmentName: string) => {
    return `transition-all duration-500 ${activeSegment === segmentName ? 'text-green-400 scale-110' : 'text-muted-foreground'}`;
  };

  return (
    <div className="w-full p-4 border rounded-md bg-card flex flex-col items-center justify-center gap-4">
      <h2 className="text-lg font-semibold">Network Flow Overview</h2>
      <div className="flex items-center justify-around w-full max-w-3xl">
        <div className={`flex flex-col items-center p-2 rounded-lg ${getSegmentClasses('mobile-to-server')}`}>
          <Phone className="h-10 w-10" />
          <span className="text-sm mt-1">Mobile</span>
        </div>

        <ArrowRight className={`h-8 w-8 ${getSegmentClasses('mobile-to-server')}`} />

        <div className={`flex flex-col items-center p-2 rounded-lg ${getSegmentClasses('server-queue')}`}>
          <div className="relative">
            <Server className="h-10 w-10" />
            {processingMode === 'split' && (
              <span className="absolute -top-2 -right-2 bg-primary text-primary-foreground rounded-full px-2 py-1 text-xs font-bold">
                {queueSize}
              </span>
            )}
          </div>
          <span className="text-sm mt-1">Server Queue</span>
        </div>

        {isWaiting && (
            <div className={`flex flex-col items-center p-2 rounded-lg text-amber-400`}>
                <Hourglass className="h-8 w-8 animate-spin" />
                <span className="text-xs mt-1">Waiting...</span>
            </div>
        )}

        <ArrowRight className={`h-8 w-8 ${getSegmentClasses('server-processing')}`} />

        <div className={`flex flex-col items-center p-2 rounded-lg ${getSegmentClasses('server-processing')}`}>
          <Server className="h-10 w-10" />
          <span className="text-sm mt-1">Processing</span>
        </div>

        <ArrowRight className={`h-8 w-8 ${getSegmentClasses('server-to-dashboard')}`} />

        <div className={`flex flex-col items-center p-2 rounded-lg ${getSegmentClasses('server-to-dashboard')}`}>
          <Globe className="h-10 w-10" />
          <span className="text-sm mt-1">Dashboard</span>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-x-8 gap-y-2 w-full max-w-2xl text-sm text-muted-foreground mt-2">
        <p><strong>Mode:</strong> {processingMode.toUpperCase()}</p>
        {llmProcessingStats && (
          <p><strong>LLM Scenes:</strong> {llmProcessingStats.scenes_analyzed}</p>
        )}
        {visionProcessingStats && (
          <p><strong>Vision Frames:</strong> {visionProcessingStats.frames_processed}</p>
        )}
      </div>
    </div>
  );
};

export default NetworkFlowVisualizer;
