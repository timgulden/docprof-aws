interface MessageAudioProps {
  audioUrl: string;
}

/**
 * Component for displaying audio player in a message.
 */
export const MessageAudio = ({ audioUrl }: MessageAudioProps) => {
  return (
    <audio controls className="mt-3 w-full">
      <source src={audioUrl} />
      Your browser does not support the audio element.
    </audio>
  );
};

