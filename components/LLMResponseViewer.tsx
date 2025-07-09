import React from 'react';

interface LLMResponseViewerProps {
  response: string | null;
}

const LLMResponseViewer: React.FC<LLMResponseViewerProps> = ({ response }) => {
  return (
    <div className="bg-card text-card-foreground rounded-lg p-4 h-full flex flex-col">
      <h3 className="text-lg font-semibold mb-2">LLM Scene Description</h3>
      <div className="flex-1 overflow-y-auto text-sm">
        {response ? (
          <p className="whitespace-pre-wrap">{response}</p>
        ) : (
          <p className="text-muted-foreground">Awaiting LLM analysis...</p>
        )}
      </div>
    </div>
  );
};

export default LLMResponseViewer;
