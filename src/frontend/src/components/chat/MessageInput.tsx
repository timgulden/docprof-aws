import type { FormEvent, KeyboardEvent } from "react";
import { useState } from "react";

interface MessageInputProps {
  onSubmit: (text: string) => Promise<void>;
  isSending: boolean;
  placeholder?: string;
}

/**
 * Component for message input form with multiline textarea and submit button.
 */
export const MessageInput = ({
  onSubmit,
  isSending,
  placeholder = "Ask a question about valuation, M&A, or corporate finance...",
}: MessageInputProps) => {
  const [message, setMessage] = useState("");

  const handleSubmit = async (event?: FormEvent<HTMLFormElement>) => {
    if (event) {
      event.preventDefault();
    }
    if (!message.trim() || isSending) {
      return;
    }

    const messageText = message.trim();
    // Clear input immediately (before async operation)
    setMessage("");
    await onSubmit(messageText);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // Submit on Enter (without Shift), allow Shift+Enter for new line
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  };

  return (
    <form onSubmit={handleSubmit} className="border-t bg-white px-4 py-3">
      <div className="flex gap-2 items-end">
        <textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          rows={3}
          className="flex-1 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100 resize-none"
          disabled={isSending}
        />

        <button
          type="submit"
          disabled={isSending || !message.trim()}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300 mb-0.5"
        >
          {isSending ? "Sending..." : "Send"}
        </button>
      </div>
    </form>
  );
};

