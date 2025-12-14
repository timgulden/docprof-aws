import { useState } from "react";
import { Play } from "lucide-react";
import { MessageContent } from "../chat/MessageContent";
import type { SourceCitation } from "../../types/chat";

interface QAExchange {
  question: string;
  answer: string;
  sources: SourceCitation[];
  audioUrl?: string;
}

interface QACard {
  paragraphIndex: number;
  exchanges: QAExchange[];
}

interface QACardProps {
  card: QACard;
  cardIndex: number;
  cardId: string;
  paragraphIndex: number;
  isThisCardLoading: boolean;
  playbackSpeed: number;
  onFollowUp: (cardIndex: number, question: string) => void;
  onResumeLecture: () => void;
  onCitationClick: (citationId: string, sources: SourceCitation[]) => void;
  onGenerateAudio?: (cardIndex: number, exchangeIndex: number, answerText: string) => Promise<void>;
}

export const QACard = ({
  card,
  cardIndex,
  cardId,
  paragraphIndex,
  isThisCardLoading,
  playbackSpeed,
  onFollowUp,
  onResumeLecture,
  onCitationClick,
  onGenerateAudio,
}: QACardProps) => {
  // Generate unique IDs for this card
  const cardIdPrefix = paragraphIndex === -1 ? 'end' : paragraphIndex.toString();
  const followupInputId = `followup-input-${cardIdPrefix}-${cardIndex}`;
  const resumeButtonId = `resume-button-${cardIdPrefix}-${cardIndex}`;
  
  // Track which exchange is generating audio
  const [generatingAudioFor, setGeneratingAudioFor] = useState<number | null>(null);

  const handlePlayAudio = async (exchange: QAExchange, exIdx: number) => {
    // If audioUrl is missing, generate it first
    if (!exchange.audioUrl && onGenerateAudio) {
      setGeneratingAudioFor(exIdx);
      try {
        await onGenerateAudio(cardIndex, exIdx, exchange.answer);
      } catch (error) {
        console.error("Failed to generate audio:", error);
        setGeneratingAudioFor(null);
        return;
      }
      setGeneratingAudioFor(null);
      // After generation, the parent will update the exchange with audioUrl
      // The user will need to click play again, or we could auto-play here
      // For now, we'll just return and let the user click again
      return;
    }
    
    // If we're still generating, don't do anything
    if (generatingAudioFor === exIdx) {
      return;
    }
    
    // If audioUrl is still missing, can't play
    if (!exchange.audioUrl) {
      return;
    }
    
    const audioId = `qa-audio-${cardIdPrefix}-${cardIndex}-${exIdx}`;
    let audio = document.getElementById(audioId) as HTMLAudioElement;
    
    if (!audio) {
      // Create audio element
      audio = new Audio(exchange.audioUrl);
      audio.id = audioId;
      audio.preload = 'auto';
      audio.playbackRate = playbackSpeed; // Use lecture playback speed
      document.body.appendChild(audio);
      
      // Clean up when audio ends
      audio.addEventListener('ended', () => {
        audio.remove();
      });
    } else {
      // Update source if it changed and audio is paused
      if (exchange.audioUrl && audio.src !== exchange.audioUrl && audio.paused) {
        audio.src = exchange.audioUrl;
        audio.playbackRate = playbackSpeed;
      } else {
        // Ensure playback speed is set
        audio.playbackRate = playbackSpeed;
      }
    }
    
    if (audio.paused) {
      audio.play();
    } else {
      audio.pause();
    }
  };

  const handleFollowUpSubmit = () => {
    const textarea = document.getElementById(followupInputId) as HTMLTextAreaElement;
    if (textarea && textarea.value.trim()) {
      onFollowUp(cardIndex, textarea.value);
      textarea.value = '';  // Clear after submit
    }
  };

  return (
    <div
      id={`qa-card-${cardIdPrefix}`}
      className="my-4 p-4 bg-white border-2 border-green-200 rounded-lg shadow-sm"
    >
      {/* All Q&A exchanges */}
      {card.exchanges.map((exchange, exIdx) => (
        <div key={exIdx} className="mb-3">
          {/* Question */}
          <div className="mb-2">
            <h4 className="font-semibold text-gray-700 mb-1">
              Question {exIdx + 1}:
            </h4>
            <p className="text-gray-800">{exchange.question}</p>
          </div>
          
          {/* Answer */}
          <div className="p-3 bg-green-50 rounded mb-3">
            <div className="flex items-center justify-between mb-2">
              <h4 className="font-semibold text-green-900">
                Answer {exIdx + 1}:
              </h4>
              {generatingAudioFor === exIdx ? (
                <span className="text-xs text-gray-400">Generating audio...</span>
              ) : exchange.audioUrl ? (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handlePlayAudio(exchange, exIdx);
                  }}
                  className="p-1.5 rounded-full bg-green-600 text-white hover:bg-green-700"
                  title="Play answer audio"
                >
                  <Play className="w-4 h-4" />
                </button>
              ) : (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handlePlayAudio(exchange, exIdx);
                  }}
                  className="p-1.5 rounded-full bg-gray-400 text-white hover:bg-gray-500"
                  title="Generate and play answer audio"
                >
                  <Play className="w-4 h-4" />
                </button>
              )}
            </div>
            <MessageContent
              content={exchange.answer}
              sources={exchange.sources}
              onCitationClick={onCitationClick}
            />
          </div>
        </div>
      ))}
      
      {/* Always show follow-up input at bottom */}
      <div className="pt-3 border-t border-gray-200">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Follow-up Question:
        </label>
        <textarea
          rows={2}
          className="w-full p-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Ask another question..."
          id={followupInputId}
        />
        <button
          onClick={handleFollowUpSubmit}
          disabled={isThisCardLoading}
          className="mt-2 px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400"
        >
          {isThisCardLoading ? 'Getting answer...' : 'Submit'}
        </button>
      </div>
      
      {/* Resume Lecture button */}
      <div className="pt-2 border-t border-gray-200 mt-3">
        <button
          id={resumeButtonId}
          onClick={onResumeLecture}
          className="px-3 py-1 text-sm bg-gray-600 text-white rounded hover:bg-gray-700 flex items-center gap-1"
        >
          <Play className="w-3 h-3" />
          Resume Lecture
        </button>
      </div>
    </div>
  );
};

