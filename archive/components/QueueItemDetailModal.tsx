import React from 'react';
import { X } from 'lucide-react';

interface QueueItemDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  itemData: any; // This will be the full queue item data
}

const QueueItemDetailModal: React.FC<QueueItemDetailModalProps> = ({ isOpen, onClose, itemData }) => {
  if (!isOpen || !itemData) {
    return null;
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-card text-card-foreground rounded-lg shadow-lg w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex justify-between items-center p-4 border-b border-border">
          <h3 className="text-lg font-semibold">Queued Frame Details: {itemData.frame_id?.substring(0, 8)}...</h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X size={24} />
          </button>
        </div>
        <div className="p-4 flex-1 overflow-y-auto text-sm">
          <pre className="bg-gray-900 text-white p-2 rounded-md overflow-x-auto text-xs">
            {JSON.stringify(itemData, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
};

export default QueueItemDetailModal;
