import React from 'react';

interface IncomingDataViewerProps {
  data: {
    frame_id: string;
    timestamp: number;
    vlm_analysis?: {
      vlm_description?: string;
      detections?: Array<{ label: string; bbox: number[]; confidence: number }>;
    };
  } | null;
}

const IncomingDataViewer: React.FC<IncomingDataViewerProps> = ({ data }) => {
  if (!data) {
    return (
      <div className="bg-card text-card-foreground rounded-lg p-4 h-full">
        <h3 className="text-lg font-semibold mb-2">Incoming iOS Data</h3>
        <p className="text-sm text-muted-foreground">No data received yet.</p>
      </div>
    );
  }

  const vlmDescription = data.vlm_analysis?.vlm_description || 'N/A';
  const detections = data.vlm_analysis?.detections || [];

  return (
    <div className="bg-card text-card-foreground rounded-lg p-4 h-full flex flex-col">
      <h3 className="text-lg font-semibold mb-2">Incoming iOS Data</h3>
      <div className="text-sm mb-4">
        <p><strong>Frame ID:</strong> {data.frame_id}</p>
        <p><strong>Timestamp:</strong> {new Date(data.timestamp * 1000).toLocaleString()}</p>
        <p><strong>VLM Description:</strong> {vlmDescription}</p>
        <p><strong>Detections:</strong> {detections.length}</p>
      </div>

      <div className="relative w-full h-48 bg-gray-800 rounded-md overflow-hidden">
        {/* Placeholder for the image/video feed */}
        <p className="absolute inset-0 flex items-center justify-center text-muted-foreground text-xs">Visual Representation of Detections</p>
        {detections.map((detection, index) => {
          // bbox is [x_min, y_min, x_max, y_max] normalized to 0-1
          const [x_min, y_min, x_max, y_max] = detection.bbox;

          // Convert normalized coordinates to percentage for CSS styling
          const left = x_min * 100;
          const top = y_min * 100;
          const width = (x_max - x_min) * 100;
          const height = (y_max - y_min) * 100;

          return (
            <div
              key={index}
              className="absolute border-2 border-red-500 text-red-500 text-xs font-bold flex items-start justify-start"
              style={{
                left: `${left}%`,
                top: `${top}%`,
                width: `${width}%`,
                height: `${height}%`,
              }}
            >
              <span className="bg-red-500 text-white px-1 py-0.5 rounded-br-md">
                {detection.label} ({Math.round(detection.confidence * 100)}%)
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default IncomingDataViewer;
