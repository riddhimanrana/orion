import React from 'react';

interface PacketEvent {
  event_type: string;
  timestamp: number;
  source: string;
  destination: string;
  summary: string;
  payload: Record<string, any>;
}

interface PacketTimelineProps {
  packetEvents: PacketEvent[];
  onSelectPacket: (packet: PacketEvent) => void;
  selectedPacket: PacketEvent | null;
}

const PacketTimeline: React.FC<PacketTimelineProps> = ({ packetEvents, onSelectPacket, selectedPacket }) => {
  return (
    <div className="h-full flex flex-col">
      <h2 className="text-lg font-semibold mb-2">Packet Timeline</h2>
      <div className="flex-1 overflow-y-auto border rounded-md p-2 bg-background">
        {packetEvents.length === 0 ? (
          <p className="text-muted-foreground text-sm">No packet events received yet.</p>
        ) : (
          <ul className="space-y-1">
            {packetEvents.map((event, index) => (
              <li
                key={index}
                className={`p-2 rounded-md cursor-pointer text-sm ${
                  selectedPacket?.timestamp === event.timestamp && selectedPacket?.event_type === event.event_type
                    ? 'bg-primary text-primary-foreground'
                    : 'hover:bg-muted'
                }`}
                onClick={() => onSelectPacket(event)}
              >
                <div className="flex justify-between items-center">
                  <span className="font-medium">{event.event_type}</span>
                  <span className="text-xs text-muted-foreground">
                    {new Date(event.timestamp * 1000).toLocaleTimeString()}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">{event.summary}</p>
                <p className="text-xs text-muted-foreground">
                  <span className="font-mono">{event.source}</span> &rarr; <span className="font-mono">{event.destination}</span>
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

export default PacketTimeline;
