/**
 * Voice Control Test Component
 * 
 * Isolated test component to debug voice control issues without the complexity
 * of the full SectionPlayer component.
 */

import { useState, useEffect, useReducer, useRef } from "react";
import { useVoiceControl } from "../../hooks/useVoiceControl";
import { reduceVoiceEvent, type VoiceModeStateMachine, type VoiceEvent } from "../../logic/voiceModeStateMachine";

export const VoiceControlTest = () => {
  // Store pending commands from state machine
  const pendingCommandsRef = useRef<Array<{ type: string; [key: string]: any }>>([]);
  // Track recent events for debugging
  const [recentEvents, setRecentEvents] = useState<Array<{ time: string; event: string }>>([]);
  
  const addEvent = (event: string) => {
    setRecentEvents(prev => [
      { time: new Date().toLocaleTimeString(), event },
      ...prev.slice(0, 9) // Keep last 10 events
    ]);
  };
  
  // Use the state machine reducer like SectionPlayer does
  const [voiceState, dispatchVoiceEvent] = useReducer(
    (state: VoiceModeStateMachine, event: VoiceEvent): VoiceModeStateMachine => {
      try {
        console.log(`[Test] State machine event: ${event.type}, current state: ${state.state}`);
        addEvent(`Reducer: ${event.type} (state: ${state.state})`);
        const result = reduceVoiceEvent(state, event);
        console.log(`[Test] State machine transition: ${state.state} -> ${result.newState.state}, commands:`, result.commands.map(c => c.type));
        addEvent(`Transition: ${state.state} -> ${result.newState.state}`);
        // Store commands to execute
        pendingCommandsRef.current = result.commands;
        console.log(`[Test] Returning new state:`, result.newState);
        return result.newState;
      } catch (error) {
        console.error("[Test] Error in state machine reducer:", error);
        addEvent(`ERROR: ${error}`);
        return state;
      }
    },
    {
      state: "idle",
      isEnabled: false,
      savedPlaybackPosition: null,
      pendingQuestion: null,
      pendingCommand: null,
    }
  );

  const voiceModeEnabled = voiceState.isEnabled;
  const voiceModeState = voiceState.state;
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  const voiceControl = useVoiceControl({
    voiceModeEnabled,
    voiceModeState,
    onEvent: (event) => {
      console.log("[Test] Voice event received:", event);
      addEvent(`Event: ${event.type}`);
      // Dispatch to state machine - it will handle all transitions
      dispatchVoiceEvent(event);
      // Note: State transition will be logged by the reducer
    },
    onVoiceModeToggle: (enabled) => {
      console.log("[Test] Voice mode toggle:", enabled);
      // Dispatch state machine event instead of directly setting state
      dispatchVoiceEvent(enabled ? { type: "VOICE_MODE_ENABLED" } : { type: "VOICE_MODE_DISABLED" });
    },
    audioRef,
    isPlaying,
    setIsPlaying,
    handlePlayPause: async () => {
      console.log("[Test] handlePlayPause called");
      setIsPlaying(!isPlaying);
    },
  });

  const {
    isListening,
    mode,
    error,
    message,
    startListeningRef,
    stopListeningRef,
  } = voiceControl;

  // Execute commands from state machine (like SectionPlayer does)
  // Use a separate effect that watches voiceState.state to ensure state has updated
  useEffect(() => {
    const commands = [...pendingCommandsRef.current];
    pendingCommandsRef.current = []; // Clear after copying
    
    if (commands.length > 0) {
      console.log("[Test] Executing commands:", commands, "Current state:", voiceState.state);
      addEvent(`Executing ${commands.length} command(s) in state: ${voiceState.state}`);
      commands.forEach(command => {
        switch (command.type) {
          case "START_WAKE_WORD_LISTENING":
            console.log("[Test] START_WAKE_WORD_LISTENING - wake word detection handled by hook");
            break;
          case "STOP_WAKE_WORD_LISTENING":
            console.log("[Test] STOP_WAKE_WORD_LISTENING - wake word detection handled by hook");
            break;
          case "START_COMMAND_LISTENING":
            console.log("[Test] START_COMMAND_LISTENING - starting command listening");
            addEvent("Command: START_COMMAND_LISTENING");
            console.log("[Test] Current state:", voiceState.state, "shouldUseContinuous should be true");
            // Try multiple times with increasing delays to ensure hook has updated
            const tryStartListening = (attempt: number, delay: number) => {
              setTimeout(() => {
                if (startListeningRef.current) {
                  console.log(`[Test] Attempt ${attempt}: Starting listening (delay ${delay}ms)`);
                  addEvent(`Start attempt ${attempt} (${delay}ms)`);
                  try {
                    startListeningRef.current();
                    // Check if it actually started after a short delay
                    setTimeout(() => {
                      console.log(`[Test] After start attempt ${attempt}, isListening:`, isListening);
                      addEvent(`After attempt ${attempt}: isListening=${isListening}`);
                    }, 200);
                  } catch (err) {
                    console.error(`[Test] Error on attempt ${attempt}:`, err);
                    addEvent(`Error on attempt ${attempt}`);
                    if (attempt < 3) {
                      tryStartListening(attempt + 1, delay + 100);
                    }
                  }
                } else {
                  console.warn(`[Test] startListeningRef is null on attempt ${attempt}!`);
                  addEvent(`Ref null on attempt ${attempt}`);
                  if (attempt < 3) {
                    tryStartListening(attempt + 1, delay + 100);
                  }
                }
              }, delay);
            };
            // Log current state info
            addEvent(`State when executing: ${voiceState.state}`);
            addEvent(`shouldUseContinuous: ${voiceModeState === "command_listening" || voiceModeState === "listening_for_question" || voiceModeState === "awaiting_resume" || voiceModeState === "awaiting_navigation"}`);
            // Try immediately, then with delays
            tryStartListening(1, 0);
            tryStartListening(2, 150);
            tryStartListening(3, 300);
            break;
          case "STOP_COMMAND_LISTENING":
            console.log("[Test] STOP_COMMAND_LISTENING - stopping command listening");
            stopListeningRef.current?.();
            break;
          case "SPEAK_TTS":
            console.log(`[Test] SPEAK_TTS: "${command.text}"`);
            // In test, just log it
            break;
          default:
            console.log(`[Test] Unhandled command: ${command.type}`);
        }
      });
    }
  }, [voiceState.state, voiceState.isEnabled, startListeningRef, stopListeningRef, isListening]);

  // Log state changes
  useEffect(() => {
    const stateInfo = {
      voiceModeEnabled,
      voiceModeState,
      isListening,
      mode,
      error: error?.message,
      message,
    };
    console.log("[Test] State update:", stateInfo);
    
    // Also show alert for important state changes
    if (voiceModeState === "command_listening" && !isListening) {
      console.warn("[Test] ⚠️ In command_listening state but NOT listening!");
    }
    if (voiceModeState === "wake_word_listening" && isListening) {
      console.warn("[Test] ⚠️ In wake_word_listening state but IS listening (should only be wake word detection)!");
    }
  }, [voiceModeEnabled, voiceModeState, isListening, mode, error, message]);
  
  // Log when state machine state changes
  useEffect(() => {
    console.log("[Test] State machine state changed:", voiceState.state, "isEnabled:", voiceState.isEnabled);
    
    // If we're in command_listening but not listening, show a warning
    if (voiceState.state === "command_listening" && !isListening) {
      console.warn("[Test] ⚠️ STATE MISMATCH: command_listening but isListening is false!");
      console.warn("[Test] This suggests startListening() was called but onstart never fired");
    }
  }, [voiceState.state, voiceState.isEnabled, isListening]);

  // Log refs
  useEffect(() => {
    console.log("[Test] Refs:", {
      hasStartListening: !!startListeningRef.current,
      hasStopListening: !!stopListeningRef.current,
    });
  }, [startListeningRef, stopListeningRef]);

  return (
    <div className="p-8 space-y-4">
      <h1 className="text-2xl font-bold">Voice Control Test</h1>
      
      <div className="space-y-2">
        <div>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={voiceModeEnabled}
              onChange={(e) => {
                console.log("[Test] Toggling voice mode:", e.target.checked);
                dispatchVoiceEvent(e.target.checked ? { type: "VOICE_MODE_ENABLED" } : { type: "VOICE_MODE_DISABLED" });
              }}
            />
            <span>Voice Mode Enabled</span>
          </label>
        </div>

        <div className="p-4 bg-gray-100 rounded">
          <h2 className="font-semibold mb-2">State:</h2>
          <ul className="space-y-1 text-sm">
            <li><strong>Voice Mode:</strong> {voiceModeEnabled ? "✅ ON" : "❌ OFF"}</li>
            <li><strong>Voice State:</strong> <span className={`font-mono ${voiceModeState === "command_listening" ? "text-green-600 font-bold" : voiceModeState === "wake_word_listening" ? "text-blue-600" : ""}`}>{voiceModeState}</span></li>
            <li><strong>Mode:</strong> {mode}</li>
            <li><strong>Is Listening:</strong> <span className={isListening ? "text-green-600 font-bold" : "text-red-600"}>{isListening ? "✅ YES" : "❌ NO"}</span></li>
            <li><strong>Error:</strong> {error?.message || "None"}</li>
            <li><strong>Message:</strong> {message || "None"}</li>
          </ul>
        </div>
        
        <div className="p-4 bg-yellow-50 rounded border-2 border-yellow-300">
          <h2 className="font-semibold mb-2">Debug Info:</h2>
          <ul className="space-y-1 text-xs font-mono">
            <li>shouldUseContinuous: {voiceModeState === "command_listening" || voiceModeState === "listening_for_question" || voiceModeState === "awaiting_resume" || voiceModeState === "awaiting_navigation" ? "true" : "false"}</li>
            <li>startListeningRef: {startListeningRef.current ? "✅ Set" : "❌ Null"}</li>
            <li>stopListeningRef: {stopListeningRef.current ? "✅ Set" : "❌ Null"}</li>
          </ul>
        </div>

        <div className="p-4 bg-blue-50 rounded">
          <h2 className="font-semibold mb-2">Instructions:</h2>
          <ol className="list-decimal list-inside space-y-1 text-sm">
            <li>Enable Voice Mode</li>
            <li>Say "DocProf" - you should see isListening change to YES</li>
            <li>Say a command like "play" or "pause"</li>
            <li>Check the console for detailed logs</li>
          </ol>
        </div>

        {voiceModeState === "command_listening" && !isListening && (
          <div className="p-4 bg-red-100 rounded border-2 border-red-400">
            <h2 className="font-semibold mb-2 text-red-800">⚠️ Issue Detected:</h2>
            <p className="text-sm text-red-700">
              State is <code className="bg-white px-1 rounded">command_listening</code> but <strong>isListening is NO</strong>.
              This means the command listening didn't start properly.
            </p>
            <button
              onClick={() => {
                console.log("[Test] Manual start listening attempt");
                addEvent("Manual start button clicked");
                startListeningRef.current?.();
                setTimeout(() => {
                  addEvent(`After manual start: isListening=${isListening}`);
                }, 200);
              }}
              className="mt-2 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
            >
              Try Manual Start
            </button>
          </div>
        )}
        
        <div className="p-4 bg-purple-50 rounded border-2 border-purple-300">
          <h2 className="font-semibold mb-2">Recent Events:</h2>
          <div className="space-y-1 text-xs font-mono max-h-40 overflow-y-auto bg-white p-2 rounded">
            {recentEvents.length === 0 ? (
              <p className="text-gray-500">No events yet...</p>
            ) : (
              recentEvents.map((e, i) => (
                <div key={i} className="flex gap-2 border-b border-gray-200 pb-1">
                  <span className="text-gray-500 w-20">{e.time}</span>
                  <span className="flex-1">{e.event}</span>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="p-4 bg-yellow-50 rounded">
          <h2 className="font-semibold mb-2">Manual Controls:</h2>
          <div className="flex gap-2">
            <button
              onClick={() => {
                console.log("[Test] Manual startListening");
                addEvent("Manual Start button clicked");
                startListeningRef.current?.();
                setTimeout(() => {
                  addEvent(`After manual start: isListening=${isListening}`);
                }, 200);
              }}
              className="px-4 py-2 bg-blue-500 text-white rounded"
            >
              Start Listening
            </button>
            <button
              onClick={() => {
                console.log("[Test] Manual stopListening");
                addEvent("Manual Stop button clicked");
                stopListeningRef.current?.();
              }}
              className="px-4 py-2 bg-red-500 text-white rounded"
            >
              Stop Listening
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

