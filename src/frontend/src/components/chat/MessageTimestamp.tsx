import { formatTimestamp } from "../../utils/formatting";

interface MessageTimestampProps {
  timestamp: string;
  role: "user" | "assistant";
}

/**
 * Component for displaying message timestamp.
 */
export const MessageTimestamp = ({ timestamp, role }: MessageTimestampProps) => {
  const formattedTime = formatTimestamp(timestamp);

  return (
    <div
      className={`mt-2 text-right text-[10px] uppercase tracking-wide ${
        role === "user" ? "text-white/70" : "text-slate-500"
      }`}
    >
      {formattedTime}
    </div>
  );
};

