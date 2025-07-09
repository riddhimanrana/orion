import React, { useState } from 'react';
import { ChevronRight, ChevronDown } from 'lucide-react';
import ContextDetailModal from './ContextDetailModal'; // Import the new modal component

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
  historicalContext?: any[]; // Add historical context prop
}

// A simple recursive component to render tree nodes
const TreeNode: React.FC<{ node: LLMReasoningNode }> = ({ node }) => {
  const [isCollapsed, setIsCollapsed] = useState(false);

  const hasChildren = node.children && node.children.length > 0;

  return (
    <li key={node.id} className="mt-1">
      <div
        className={`flex items-center cursor-pointer hover:bg-muted-foreground/10 rounded-sm p-1 ${hasChildren ? '' : 'ml-4'}`}
        onClick={() => hasChildren && setIsCollapsed(!isCollapsed)}
      >
        {hasChildren && (
          <span className="mr-1">
            {isCollapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
          </span>
        )}
        <span className="font-semibold text-foreground">{node.name}: </span>
        {typeof node.value === 'object' && node.value !== null ? (
          <span className="text-muted-foreground italic">(Object)</span>
        ) : (
          <span className="text-accent-foreground">{String(node.value)}</span>
        )}
      </div>
      {!isCollapsed && hasChildren && (
        <ul className="ml-4 pl-2 border-l border-border">
          {node.children?.map(child => <TreeNode key={child.id} node={child} />)}
        </ul>
      )}
    </li>
  );
};


const LLMReasoningTree: React.FC<LLMReasoningTreeProps> = ({ reasoningData, historicalContext }) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedContextData, setSelectedContextData] = useState<any>(null);

  const handleHistoricalContextClick = (entry: any) => {
    setSelectedContextData(entry);
    setIsModalOpen(true);
  };

  const rootNodes: LLMReasoningNode[] = [];

  if (reasoningData) {
    rootNodes.push(reasoningData);
  }

  if (historicalContext && historicalContext.length > 0) {
    const historicalRoot: LLMReasoningNode = {
      id: "historical-context",
      name: "Historical Context",
      children: historicalContext.map((entry, index) => ({
        id: `hist-${entry.frame_id || index}`,
        name: `Frame ${entry.frame_id || index}`,
        value: entry.analysis?.scene_description || "N/A", // Display summary in tree
        // Make this node clickable to open modal
        onClick: () => handleHistoricalContextClick(entry),
      }))
    };
    rootNodes.push(historicalRoot);
  }

  return (
    <div className="bg-muted border rounded-lg p-4 h-full overflow-y-auto">
      <h2 className="text-lg font-semibold mb-2 text-foreground">LLM Reasoning & Context</h2>
      {rootNodes.length > 0 ? (
        <ul className="text-sm">
          {rootNodes.map(node => {
            // Special handling for historical context nodes to make them clickable
            if (node.id.startsWith("hist-") && node.onClick) {
              return (
                <li key={node.id} className="mt-1">
                  <div
                    className="flex items-center cursor-pointer hover:bg-muted-foreground/10 rounded-sm p-1"
                    onClick={node.onClick}
                  >
                    <span className="font-semibold text-foreground">{node.name}: </span>
                    <span className="text-accent-foreground">{String(node.value)}</span>
                  </div>
                </li>
              );
            } else if (node.id === "historical-context" && node.children) {
                // Render the Historical Context root node with its children as clickable items
                return (
                    <li key={node.id} className="mt-1">
                        <div className="flex items-center font-semibold text-foreground p-1">
                            {node.name}
                        </div>
                        <ul className="ml-4 pl-2 border-l border-border">
                            {node.children.map(child => (
                                <li key={child.id} className="mt-1">
                                    <div
                                        className="flex items-center cursor-pointer hover:bg-muted-foreground/10 rounded-sm p-1"
                                        onClick={child.onClick}
                                    >
                                        <span className="font-semibold text-foreground">{child.name}: </span>
                                        <span className="text-accent-foreground">{String(child.value)}</span>
                                    </div>
                                </li>
                            ))}
                        </ul>
                    </li>
                );
            }
            return <TreeNode key={node.id} node={node} />;
          })}
        </ul>
      ) : (
        <p className="text-muted-foreground">No LLM reasoning or historical context data yet.</p>
      )}

      <ContextDetailModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        contextData={selectedContextData}
      />
    </div>
  );
};

export default LLMReasoningTree;