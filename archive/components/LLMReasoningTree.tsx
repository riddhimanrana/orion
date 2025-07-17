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
          <span className="text-accent-foreground">{JSON.stringify(node.value, null, 2)}</span>
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

  return (
    <div className="bg-muted border rounded-lg p-4 h-full overflow-y-auto">
      <h2 className="text-lg font-semibold mb-2 text-foreground">LLM Reasoning & Context</h2>
      {rootNodes.length > 0 || (historicalContext && historicalContext.length > 0) ? (
        <ul className="text-sm">
          {rootNodes.map(node => <TreeNode key={node.id} node={node} />)}
          {historicalContext && historicalContext.length > 0 && (
            <li className="mt-1">
              <div className="flex items-center font-semibold text-foreground p-1">
                Historical Context
              </div>
              <ul className="ml-4 pl-2 border-l border-border">
                {historicalContext.map((entry, index) => (
                  <li key={`hist-${entry.frame_id || index}`} className="mt-1">
                    <div
                      className="flex items-center cursor-pointer hover:bg-muted-foreground/10 rounded-sm p-1"
                      onClick={() => handleHistoricalContextClick(entry)}
                    >
                      <span className="font-semibold text-foreground">Frame {entry.frame_id?.substring(0, 8)}...: </span>
                      <span className="text-accent-foreground truncate">{entry.analysis?.scene_description || entry.vlm_description || "N/A"}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </li>
          )}
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