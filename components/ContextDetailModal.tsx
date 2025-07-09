import React from 'react';
import { X } from 'lucide-react';

interface ContextDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  contextData: any; // This will be the full historical context entry
}

const ContextDetailModal: React.FC<ContextDetailModalProps> = ({ isOpen, onClose, contextData }) => {
  if (!isOpen || !contextData) {
    return null;
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-card text-card-foreground rounded-lg shadow-lg w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex justify-between items-center p-4 border-b border-border">
          <h3 className="text-lg font-semibold">Historical Frame Details: {contextData.frame_id?.substring(0, 8)}...</h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X size={24} />
          </button>
        </div>
        <div className="p-4 flex-1 overflow-y-auto text-sm">
          <p className="mb-2"><strong>Timestamp:</strong> {new Date(contextData.timestamp * 1000).toLocaleString()}</p>
          
          {contextData.vlm_description && (
            <div className="mb-4">
              <h4 className="font-semibold mb-1">VLM Description:</h4>
              <p className="bg-muted p-2 rounded-md whitespace-pre-wrap">{contextData.vlm_description}</p>
            </div>
          )}

          {contextData.analysis?.scene_description && (
            <div className="mb-4">
              <h4 className="font-semibold mb-1">LLM Scene Description:</h4>
              <p className="bg-muted p-2 rounded-md whitespace-pre-wrap">{contextData.analysis.scene_description}</p>
            </div>
          )}

          {contextData.detections && contextData.detections.length > 0 && (
            <div className="mb-4">
              <h4 className="font-semibold mb-1">Detections:</h4>
              <div className="relative w-full h-48 bg-gray-800 rounded-md overflow-hidden">
                <p className="absolute inset-0 flex items-center justify-center text-muted-foreground text-xs">Simplified Detections View</p>
                {contextData.detections.map((detection: any, index: number) => {
                  const [x_min, y_min, x_max, y_max] = detection.bbox;
                  const left = x_min * 100;
                  const top = y_min * 100;
                  const width = (x_max - x_min) * 100;
                  const height = (y_max - y_min) * 100;

                  return (
                    <div
                      key={index}
                      className="absolute border-2 border-blue-400 text-blue-400 text-xs font-bold flex items-start justify-start"
                      style={{
                        left: `${left}%`,
                        top: `${top}%`,
                        width: `${width}%`,
                        height: `${height}%`,
                      }}
                    >
                      <span className="bg-blue-400 text-white px-1 py-0.5 rounded-br-md">
                        {detection.label} ({Math.round(detection.confidence * 100)}%)
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Display raw JSON for debugging */}
          <div className="mt-4">
            <h4 className="font-semibold mb-1">Raw Data:</h4>
            <pre className="bg-gray-900 text-white p-2 rounded-md overflow-x-auto text-xs">
              {JSON.stringify(contextData, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ContextDetailModal;
