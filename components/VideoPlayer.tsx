import React from 'react';

interface VideoPlayerProps {
  frameData: string | null; // Expecting base64 encoded image string or null
}

const VideoPlayer: React.FC<VideoPlayerProps> = ({ frameData }) => {
  return (
    <div className="bg-muted border rounded-lg h-full w-full flex items-center justify-center overflow-hidden">
      {frameData ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={`data:image/jpeg;base64,${frameData}`}
          alt="Live Video Feed"
          className="object-contain h-full w-full"
        />
      ) : (
        <p className="text-muted-foreground">Live Video Feed</p>
      )}
    </div>
  );
};

export default VideoPlayer;