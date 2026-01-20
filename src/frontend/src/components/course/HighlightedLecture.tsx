import { useMemo, useEffect, useRef } from "react";
import type { SpeechMark } from "../../api/courses";
import type { HighlightPosition } from "../../hooks/usePollyAudio";

interface HighlightedLectureProps {
  /** The lecture text to display */
  lectureScript: string;
  /** Current highlight position from audio playback */
  highlightPosition: HighlightPosition;
  /** Speech marks for mapping text positions */
  speechMarks: SpeechMark[];
  /** Whether audio is currently playing */
  isPlaying: boolean;
  /** Callback when user clicks a word */
  onWordClick?: (wordIndex: number) => void;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Renders lecture text with word-level highlighting synchronized to audio playback.
 * 
 * Features:
 * - Current word highlighted in a distinct color
 * - Current sentence highlighted with subtle background
 * - Auto-scroll to keep highlighted word visible
 * - Click on any word to seek audio to that position
 */
export const HighlightedLecture = ({
  lectureScript,
  highlightPosition,
  speechMarks,
  isPlaying,
  onWordClick,
  className = "",
}: HighlightedLectureProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const currentWordRef = useRef<HTMLSpanElement>(null);
  const scrollContainerRef = useRef<HTMLElement | null>(null);
  
  // Build word marks lookup by byte offset
  const wordMarksByOffset = useMemo(() => {
    const map = new Map<number, { mark: SpeechMark; index: number }>();
    const wordMarks = speechMarks.filter(m => m.type === 'word');
    wordMarks.forEach((mark, index) => {
      map.set(mark.start, { mark, index });
    });
    return map;
  }, [speechMarks]);
  
  // Parse lecture text into segments that can be individually highlighted
  // Always create word segments to avoid layout shifts
  const segments = useMemo(() => {
    if (!lectureScript) return [];
    
    // Get word marks sorted by start position
    const wordMarks = speechMarks
      .filter(m => m.type === 'word')
      .sort((a, b) => a.start - b.start);
    
    const result: Array<{
      type: 'word' | 'space' | 'newline' | 'paragraph';
      text: string;
      key: string;
      wordIndex?: number;
      charStart?: number;
    }> = [];
    
    // If no speech marks, create simple paragraph segments to maintain consistent structure
    if (wordMarks.length === 0) {
      const paragraphs = lectureScript.split(/\n\n+/);
      for (let i = 0; i < paragraphs.length; i++) {
        if (i > 0) {
          // Add paragraph separator
          result.push({
            type: 'newline',
            text: '\n\n',
            key: `para-sep-${i}`,
          });
        }
        result.push({
          type: 'paragraph',
          text: paragraphs[i],
          key: `para-${i}`,
        });
      }
      return result;
    }
    
    let currentPos = 0;
    
    for (let i = 0; i < wordMarks.length; i++) {
      const mark = wordMarks[i];
      
      // Add any text before this word (spaces, punctuation, newlines)
      // Use character positions, not byte positions
      if (mark.start > currentPos) {
        const betweenText = lectureScript.substring(currentPos, mark.start);
        
        // Split by newlines to preserve paragraph structure
        const lines = betweenText.split(/(\n+)/);
        for (let j = 0; j < lines.length; j++) {
          const line = lines[j];
          if (line.match(/^\n+$/)) {
            result.push({
              type: 'newline',
              text: line,
              key: `newline-${currentPos}-${j}`,
            });
          } else if (line.length > 0) {
            result.push({
              type: 'space',
              text: line,
              key: `space-${currentPos}-${j}`,
            });
          }
        }
      }
      
      // Add the word using character positions
      const wordText = lectureScript.substring(mark.start, mark.end);
      result.push({
        type: 'word',
        text: wordText,
        key: `word-${i}`,
        wordIndex: i,
        charStart: mark.start,
      });
      
      currentPos = mark.end;
    }
    
    // Add any remaining text after the last word
    if (currentPos < lectureScript.length) {
      const remainingText = lectureScript.substring(currentPos);
      if (remainingText.length > 0) {
        result.push({
          type: 'space',
          text: remainingText,
          key: `space-end`,
        });
      }
    }
    
    return result;
  }, [lectureScript, speechMarks]);
  
  // Find the scrollable parent container on mount
  useEffect(() => {
    if (!containerRef.current) return;
    
    let element = containerRef.current.parentElement;
    while (element) {
      const { overflow, overflowY } = getComputedStyle(element);
      if (overflow === 'auto' || overflow === 'scroll' || overflowY === 'auto' || overflowY === 'scroll') {
        scrollContainerRef.current = element;
        console.log('Found scrollable container:', element);
        break;
      }
      element = element.parentElement;
    }
  }, []);
  
  // Auto-scroll to keep current word visible
  // Scroll strategy: Keep reading near the top, scroll up when approaching bottom
  useEffect(() => {
    if (!isPlaying || !currentWordRef.current) return;
    
    const wordEl = currentWordRef.current;
    const scrollContainer = scrollContainerRef.current;
    
    if (!scrollContainer) {
      console.warn('No scrollable container found');
      return;
    }
    
    const wordRect = wordEl.getBoundingClientRect();
    const containerRect = scrollContainer.getBoundingClientRect();
    
    // Calculate line height (approximate)
    const lineHeight = parseFloat(getComputedStyle(wordEl).lineHeight) || 24;
    
    // Check if word is above the visible area
    const isAbove = wordRect.top < containerRect.top;
    
    // Check if word is approaching the bottom (within one line from bottom)
    const isNearBottom = wordRect.bottom > containerRect.bottom - lineHeight * 2;
    
    if (isAbove || isNearBottom) {
      // Calculate target scroll position to place word one line from top
      const currentScrollTop = scrollContainer.scrollTop;
      const wordTopRelativeToContainer = wordRect.top - containerRect.top;
      const targetScrollTop = currentScrollTop + wordTopRelativeToContainer - lineHeight;
      
      scrollContainer.scrollTo({
        top: targetScrollTop,
        behavior: 'smooth',
      });
    }
  }, [highlightPosition.wordIndex, isPlaying]);
  
  // Render a word segment with appropriate highlighting
  const renderWord = (segment: typeof segments[0] & { type: 'word' }) => {
    const isCurrentWord = segment.wordIndex === highlightPosition.wordIndex;
    const isInCurrentSentence = highlightPosition.currentSentence && 
      segment.charStart !== undefined &&
      segment.charStart >= highlightPosition.currentSentence.start &&
      segment.charStart < highlightPosition.currentSentence.end;
    
    // Minimal styling to avoid layout shifts - only add background when actually highlighting
    const highlightStyle = isCurrentWord
      ? { backgroundColor: '#fde047', fontWeight: 500 }
      : isInCurrentSentence && isPlaying
        ? { backgroundColor: '#fef9c3' }
        : undefined;
    
    return (
      <span
        key={segment.key}
        ref={isCurrentWord ? currentWordRef : undefined}
        style={highlightStyle}
        onClick={() => onWordClick?.(segment.wordIndex!)}
        data-word-index={segment.wordIndex}
      >
        {segment.text}
      </span>
    );
  };
  
  // Render segments grouped by paragraphs
  const renderSegments = () => {
    const paragraphs: JSX.Element[][] = [];
    let currentParagraph: JSX.Element[] = [];
    
    for (let i = 0; i < segments.length; i++) {
      const segment = segments[i];
      
      if (segment.type === 'word') {
        currentParagraph.push(renderWord(segment as typeof segments[0] & { type: 'word' }));
      } else if (segment.type === 'newline') {
        const newlineCount = (segment.text.match(/\n/g) || []).length;
        if (newlineCount >= 2) {
          // End current paragraph and start new one
          if (currentParagraph.length > 0) {
            paragraphs.push([...currentParagraph]);
            currentParagraph = [];
          }
        } else {
          // Single newline - add a space to preserve line breaks within paragraphs
          currentParagraph.push(<span key={segment.key}> </span>);
        }
      } else if (segment.type === 'paragraph') {
        currentParagraph.push(
          <span key={segment.key}>{segment.text}</span>
        );
      } else {
        // Space or punctuation
        currentParagraph.push(<span key={segment.key}>{segment.text}</span>);
      }
    }
    
    // Add final paragraph if any
    if (currentParagraph.length > 0) {
      paragraphs.push(currentParagraph);
    }
    
    // Render each paragraph wrapped in <p> tag
    return paragraphs.map((paraSegments, idx) => (
      <p key={`para-${idx}`} className="mb-4">
        {paraSegments}
      </p>
    ));
  };
  
  return (
    <div
      ref={containerRef}
      className={`lecture-text prose prose-slate max-w-none ${className}`}
    >
      {renderSegments()}
    </div>
  );
};

/**
 * Simple version of HighlightedLecture that only shows paragraph-level highlighting.
 * Used as a fallback when speech marks are not available.
 */
export const ParagraphHighlightedLecture = ({
  lectureScript,
  currentParagraphIndex,
  className = "",
}: {
  lectureScript: string;
  currentParagraphIndex: number | null;
  className?: string;
}) => {
  const paragraphs = useMemo(() => {
    return lectureScript.split(/\n\n+/);
  }, [lectureScript]);
  
  return (
    <div className={`lecture-text prose prose-slate max-w-none ${className}`}>
      {paragraphs.map((para, idx) => (
        <p
          key={idx}
          className={`mb-4 transition-colors duration-200 ${
            idx === currentParagraphIndex
              ? "bg-yellow-100 -mx-2 px-2 rounded"
              : ""
          }`}
        >
          {para}
        </p>
      ))}
    </div>
  );
};
