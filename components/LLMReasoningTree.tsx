import React from 'react';

// Defines the structure for a node in the LLM reasoning tree
export interface LLMReasoningNode { // Exporting for use in page.tsx
  id: string;
  name: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  value?: any; // Can be string, number, object, etc.
  children?: LLMReasoningNode[];
}

interface LLMReasoningTreeProps {
  reasoningData: LLMReasoningNode | null;
}

// A simple recursive component to render tree nodes
// TODO: Enhance with shadcn/ui components (e.g., Collapsible) for better UX
const renderTreeNode = (node: LLMReasoningNode): React.ReactNode => (
  <li key={node.id} className="ml-4">
    <span className="font-semibold text-foreground">{node.name}: </span>
    {typeof node.value === 'object' && node.value !== null ? ( // Check for null as well
      <span className="text-muted-foreground italic">(Object)</span>
    ) : (
      <span className="text-accent-foreground">{String(node.value)}</span>
    )}
    {node.children && node.children.length > 0 && (
      <ul className="pl-4 border-l border-border">
        {node.children.map(renderTreeNode)}
      </ul>
    )}
  </li>
);


const LLMReasoningTree: React.FC<LLMReasoningTreeProps> = ({ reasoningData }) => {
  // TODO: Implement or integrate a more sophisticated tree view component
  // (e.g., custom with shadcn/ui Collapsible, or a library like react-json-view)

  return (
    <div className="bg-muted border rounded-lg p-4 h-full overflow-y-auto">
      <h2 className="text-lg font-semibold mb-2 text-foreground">LLM Reasoning</h2>
      {reasoningData ? (
        <ul className="text-sm">
          {renderTreeNode(reasoningData)}
        </ul>
      ) : (
        <p className="text-muted-foreground">No LLM reasoning data yet.</p>
      )}
    </div>
  );
};

export default LLMReasoningTree;