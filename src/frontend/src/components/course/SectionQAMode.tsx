import { useState } from "react";
import { ArrowLeft, Send } from "lucide-react";
import { askQAQuestion } from "../../api/courses";
import { MessageBubble } from "../chat/MessageBubble";
import type { ChatMessage } from "../../types/chat";

interface SectionQAModeProps {
  sectionId: string;
  qaSessionId: string;
  onResume: () => void;
  onComplete: () => void;
}

export const SectionQAMode = ({ sectionId, qaSessionId, onResume, onComplete }: SectionQAModeProps) => {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || loading) return;

    const userMessage: ChatMessage = {
      id: `qa-${Date.now()}`,
      role: "user",
      content: question,
      timestamp: new Date().toISOString(),
      figures: [],
    };

    setMessages((prev) => [...prev, userMessage]);
    setQuestion("");
    setLoading(true);

    try {
      const result = await askQAQuestion(sectionId, question);
      
      // TODO: Get actual answer from API response
      // For now, show a placeholder
      const assistantMessage: ChatMessage = {
        id: `qa-${Date.now()}-response`,
        role: "assistant",
        content: result.message || "Answer will appear here...",
        timestamp: new Date().toISOString(),
        figures: [],
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      console.error("Failed to ask question:", err);
      const errorMessage: ChatMessage = {
        id: `qa-${Date.now()}-error`,
        role: "assistant",
        content: "Sorry, I couldn't process your question. Please try again.",
        timestamp: new Date().toISOString(),
        figures: [],
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b bg-white flex items-center gap-4">
        <button
          onClick={onResume}
          className="p-2 rounded-md hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h2 className="text-lg font-semibold">Q&A Session</h2>
          <p className="text-sm text-gray-600">Ask questions about this section</p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 bg-slate-50 space-y-4">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center text-gray-500">
            Ask a question about this section to get started.
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            onCitationClick={() => {}}
          />
        ))}
      </div>

      {/* Input */}
      <div className="p-4 border-t bg-white">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="w-5 h-5" />
          </button>
        </form>

        {/* Actions */}
        <div className="mt-3 flex gap-2">
          <button
            onClick={onResume}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Resume Lecture
          </button>
          <button
            onClick={onComplete}
            className="flex-1 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500"
          >
            Complete Section
          </button>
        </div>
      </div>
    </div>
  );
};

