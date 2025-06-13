import React from 'react';

// Defines the structure for graph nodes
export interface Node { // Exporting for use in page.tsx
  id: string;
  label: string;
  type?: string;
  status?: string;
  timestamp?: string | number;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  properties?: Record<string, any>;
}

// Defines the structure for graph edges
export interface Edge { // Exporting for use in page.tsx
  id: string;
  source: string; // ID of the source node
  target: string; // ID of the target node
  label?: string;
  type?: string;
  strength?: number;
  timestamp?: string | number;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  properties?: Record<string, any>;
}

// Defines the overall graph data structure
export interface GraphData { // Exporting for use in page.tsx
  nodes: Node[];
  edges: Edge[];
}

interface VisionContextGraphProps {
  graphData: GraphData;
}

const VisionContextGraph: React.FC<VisionContextGraphProps> = ({ graphData }) => {
  // TODO: Integrate a graph visualization library (e.g., react-flow, vis-network)
  // For now, just display basic info or a placeholder

  return (
    <div className="bg-muted border rounded-lg p-4 h-full flex flex-col items-center justify-center">
      <h2 className="text-lg font-semibold mb-2 text-foreground self-start">Vision Context Graph</h2>
      {graphData.nodes.length === 0 && graphData.edges.length === 0 ? (
        <p className="text-muted-foreground">No graph data yet.</p>
      ) : (
        <div className="text-sm text-muted-foreground">
          <p>Nodes: {graphData.nodes.length}</p>
          <p>Edges: {graphData.edges.length}</p>
          {/* Placeholder for actual graph rendering */}
        </div>
      )}
    </div>
  );
};

export default VisionContextGraph;