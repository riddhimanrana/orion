import React from 'react';

interface QueueItem {
  frame_id: string;
  timestamp: number;
  device_id: string;
  status: string; // e.g., "enqueued", "processing"
}

interface QueueViewerProps {
  queueSize: number;
  queueContents: QueueItem[];
  onSelectQueueItem: (item: QueueItem) => void;
}

const QueueViewer: React.FC<QueueViewerProps> = ({ queueSize, queueContents, onSelectQueueItem }) => {
  return (
    <div className="bg-card text-card-foreground rounded-lg p-4 h-full flex flex-col">
      <h3 className="text-lg font-semibold mb-2">Server Queue</h3>
      <div className="text-sm mb-4">
        <p><strong>Current Queue Size:</strong> {queueSize}</p>
      </div>
      <div className="flex-1 overflow-y-auto border rounded-md p-2 bg-background">
        {queueContents.length === 0 ? (
          <p className="text-muted-foreground text-sm">Queue is empty.</p>
        ) : (
          <table className="w-full text-left table-auto">
            <thead>
              <tr className="text-xs text-muted-foreground uppercase border-b">
                <th className="py-2 px-1">Frame ID</th>
                <th className="py-2 px-1">Status</th>
                <th className="py-2 px-1">Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {queueContents.map((item, index) => (
                <tr key={item.frame_id} className="border-b border-dashed border-muted-foreground/20 last:border-b-0 cursor-pointer hover:bg-muted" onClick={() => onSelectQueueItem(item)}>
                  <td className="py-2 px-1 text-xs font-mono">{item.frame_id.substring(0, 8)}...</td>
                  <td className="py-2 px-1 text-xs">{item.status}</td>
                  <td className="py-2 px-1 text-xs">{new Date(item.timestamp * 1000).toLocaleTimeString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default QueueViewer;
