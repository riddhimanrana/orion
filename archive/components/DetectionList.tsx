import React from 'react';

// Defines the structure for a single detection
export interface Detection { // Exporting for use in page.tsx
  id: string;
  label: string;
  confidence: number;
  contextual_label?: string;
  // TODO: Add other relevant properties like bounding box coordinates (e.g., x, y, width, height)
}

interface DetectionListProps {
  detections: Detection[];
}

const DetectionList: React.FC<DetectionListProps> = ({ detections }) => {
  return (
    <div className="bg-muted border rounded-lg p-4 h-full overflow-y-auto">
      <h2 className="text-lg font-semibold mb-2 text-foreground">Detections</h2>
      {detections.length === 0 ? (
        <p className="text-muted-foreground">No detections yet.</p>
      ) : (
        <ul className="space-y-2">
          {detections.map((detection) => ( // Use detection.id for key if available and unique
            <li key={detection.id || Math.random().toString()} className="p-2 border-b border-border text-sm">
              <div className="font-medium text-foreground">{detection.contextual_label || detection.label}</div>
              <div className="text-xs text-muted-foreground">
                Confidence: {(detection.confidence * 100).toFixed(1)}%
              </div>
              {/* TODO: Display other detection details like bounding box */}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default DetectionList;