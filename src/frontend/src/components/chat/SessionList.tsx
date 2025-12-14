import { useCallback, useEffect, useState } from "react";
import { X } from "lucide-react";

import type { ChatMessage, FigureAttachment, SessionMetadata } from "../../types/chat";
import { createSession, deleteSession, getSessionWithMessages, listSessions } from "../../api/sessions";
import { useChatStore } from "../../store/chatStore";

// Shared state for session list open/close
let sessionListState: { 
  isOpen: boolean; 
  setIsOpen: (open: boolean) => void;
  loadSessions: () => Promise<void>;
} | null = null;

export const SessionList = () => {
  const [sessions, setSessions] = useState<SessionMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [isOpen, setIsOpen] = useState(false);
  const currentSessionId = useChatStore((state) => state.state.sessionId);
  const dispatch = useChatStore((state) => state.dispatch);

  const loadSessions = useCallback(async () => {
    try {
      setLoading(true);
      const sessionList = await listSessions();
      console.log("Loaded sessions:", sessionList);
      setSessions(sessionList);
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'code' in error && error.code === 'ERR_NETWORK') {
        console.error("Failed to load sessions: Network error - is the backend server running?", error);
      } else {
        console.error("Failed to load sessions:", error);
      }
      setSessions([]); // Set empty array on error so UI shows "no sessions"
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // Refresh sessions when opening the sidebar or when current session changes
  useEffect(() => {
    if (isOpen) {
      loadSessions();
    }
  }, [isOpen, currentSessionId, loadSessions]);

  // Expose state for button component
  useEffect(() => {
    sessionListState = { isOpen, setIsOpen, loadSessions };
    return () => {
      sessionListState = null;
    };
  }, [isOpen, loadSessions]);

  const handleCreateSession = async () => {
    try {
      const newSession = await createSession();
      console.log("Created new session:", newSession);
      await dispatch({
        type: "session_created",
        sessionMetadata: newSession,
      });
      // Refresh sessions after creating - wait a bit for backend to persist
      await new Promise(resolve => setTimeout(resolve, 100));
      await loadSessions();
      // Don't close sidebar - keep it open so user can see the new session
    } catch (error) {
      console.error("Failed to create session:", error);
    }
  };

  const handleSwitchSession = async (session: SessionMetadata) => {
    try {
      // Load full session data from backend
      const sessionData = await getSessionWithMessages(session.sessionId);
      
      // Convert backend messages to frontend format
      const messages: ChatMessage[] = sessionData.messages.map((msg) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        timestamp: msg.timestamp,
        figures: (msg.figures || []) as FigureAttachment[],
        audioUrl: msg.audio_url,
      }));
      
      // Restore session with full data
      await dispatch({
        type: "session_switched",
        sessionId: session.sessionId,
        snapshot: {
          sessionId: sessionData.metadata.sessionId,
          sessionName: sessionData.metadata.sessionName,
          sessionType: sessionData.metadata.sessionType,
          sessionContext: sessionData.sessionContext,
          createdAt: sessionData.metadata.createdAt,
          updatedAt: sessionData.metadata.updatedAt,
          messages,
        },
      });
      
      await loadSessions();
      setIsOpen(false);
    } catch (error) {
      console.error("Failed to load session:", error);
    }
  };

  const handleDeleteSession = async (sessionId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    try {
      await deleteSession(sessionId);
      // If deleting current session, reset
      if (sessionId === currentSessionId) {
        await dispatch({ type: "reset_requested" });
      }
      await loadSessions();
    } catch (error) {
      console.error("Failed to delete session:", error);
    }
  };

  return (
    <>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-28">
          <div className="absolute inset-0 bg-black/20" onClick={() => setIsOpen(false)} />
          <div className="relative w-80 bg-white rounded-lg shadow-lg border border-slate-200 max-h-[calc(100vh-8rem)] flex flex-col">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <h2 className="text-lg font-semibold">Chat Sessions</h2>
              <button
                onClick={() => setIsOpen(false)}
                className="rounded-md p-1 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-2 py-2">
              <button
                onClick={handleCreateSession}
                className="mb-3 w-full rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700"
              >
                + New Chat
              </button>

              {loading ? (
                <div className="py-4 text-center text-sm text-slate-500">Loading sessions...</div>
              ) : sessions.length === 0 ? (
                <div className="py-8 text-center text-sm text-slate-500">No sessions yet. Create one to get started.</div>
              ) : (
                <div className="space-y-1">
                  {sessions.map((session) => (
                    <div
                      key={session.sessionId}
                      onClick={() => handleSwitchSession(session)}
                      className={`group relative cursor-pointer rounded-md px-3 py-2 transition hover:bg-slate-50 ${
                        session.sessionId === currentSessionId ? "bg-blue-50 ring-1 ring-blue-200" : ""
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="truncate text-sm font-medium text-slate-900">
                            {session.sessionName || "Untitled Chat"}
                          </div>
                          {session.lastMessagePreview && (
                            <div className="mt-1 truncate text-xs text-slate-500">{session.lastMessagePreview}</div>
                          )}
                          <div className="mt-1 text-xs text-slate-400">
                            {new Date(session.updatedAt).toLocaleDateString()} • {session.messageCount} messages
                          </div>
                        </div>
                        <button
                          onClick={(e) => handleDeleteSession(session.sessionId, e)}
                          className="ml-2 opacity-0 transition-opacity group-hover:opacity-100"
                          title="Delete session"
                        >
                          <X className="h-4 w-4 text-slate-400 hover:text-red-600" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
};

// Button component for use in header
SessionList.Button = () => {
  return (
    <button
      onClick={() => {
        if (sessionListState) {
          sessionListState.setIsOpen(true);
          // loadSessions will be called automatically by useEffect when isOpen changes
        }
      }}
      className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700"
    >
      Sessions
    </button>
  );
};

