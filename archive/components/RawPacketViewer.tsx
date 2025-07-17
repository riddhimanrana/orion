import React from 'react';

interface PacketEvent {
  event_type: string;
  timestamp: number;
  source: string;
  destination: string;
  summary: string;
  payload: Record<string, any>;
}

interface RawPacketViewerProps {
  packet: PacketEvent | null;
}

const RawPacketViewer: React.FC<RawPacketViewerProps> = ({ packet }) => {
  if (!packet) {
    return (
      <div className="h-full flex flex-col">
        <h2 className="text-lg font-semibold mb-2">Raw Packet Data</h2>
        <div className="flex-1 overflow-y-auto border rounded-md p-2 bg-background">
          <p className="text-muted-foreground text-sm">Select a packet from the timeline to view its raw data.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <h2 className="text-lg font-semibold mb-2">Raw Packet Data</h2>
      <div className="flex-1 overflow-y-auto border rounded-md p-2 bg-background font-mono text-xs">
        <pre className="whitespace-pre-wrap break-all">
          {JSON.stringify(packet, null, 2)}
        </pre>
      </div>
    </div>
  );
};

export default RawPacketViewer;
