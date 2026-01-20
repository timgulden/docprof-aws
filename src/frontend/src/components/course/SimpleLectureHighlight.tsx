import { useEffect, useMemo, useRef } from "react";
import type { SpeechMark } from "../../api/courses";
import type { HighlightPosition } from "../../hooks/usePollyAudio";

interface SimpleLectureHighlightProps {
  lectureScript: string;
  highlightPosition: HighlightPosition;
  speechMarks: SpeechMark[];
  isPlaying: boolean;
  onWordClick?: (wordIndex: number) => void;
  className?: string;
}

/**
 * Simplified lecture component that maintains consistent rendering.
 * Uses CSS-based highlighting to avoid DOM restructuring.
 */
export const SimpleLectureHighlight = ({
  lectureScript,
  highlightPosition,
  speechMarks,
  isPlaying,
  onWordClick,
  className = "",
}: SimpleLectureHighlightProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLElement | null>(null);
  const currentWordRef = useRef<HTMLSpanElement | null>(null);

  // Get word marks for click handling
  const wordMarks = useMemo(
    () => speechMarks.filter(m => m.type === "word"),
    [speechMarks]
  );

  // Normalize text indexes to account for characters Polly likely ignores in offsets
  const offsetMap = useMemo(() => {
    const encoder = new TextEncoder();
    const charToByte: number[] = new Array(lectureScript.length + 1);
    const byteToChar: number[] = [];
    let byteIndex = 0;
    let codeUnitIndex = 0;

    for (const ch of lectureScript) {
      charToByte[codeUnitIndex] = byteIndex;
      const byteLen = encoder.encode(ch).length;
      for (let b = 0; b < byteLen; b += 1) {
        byteToChar[byteIndex + b] = codeUnitIndex;
      }
      byteIndex += byteLen;
      codeUnitIndex += ch.length;
    }

    charToByte[lectureScript.length] = byteIndex;
    byteToChar[byteIndex] = lectureScript.length;

    return {
      charToByte,
      byteToChar,
      byteLength: byteIndex,
    };
  }, [lectureScript]);

  // Find the scrollable parent container on mount
  useEffect(() => {
    if (!containerRef.current) return;
    
    let element = containerRef.current.parentElement;
    while (element) {
      const { overflow, overflowY } = getComputedStyle(element);
      if (overflow === 'auto' || overflow === 'scroll' || overflowY === 'auto' || overflowY === 'scroll') {
        scrollContainerRef.current = element;
        break;
      }
      element = element.parentElement;
    }
  }, []);

  // Highlighting with both sentence and word emphasis
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    if (!isPlaying) {
      container.textContent = lectureScript;
      currentWordRef.current = null;
      return;
    }

    const mapIndex = (idx?: number) => {
      if (idx === undefined) return undefined;
      const clamped = Math.max(0, Math.min(idx, offsetMap.byteLength));
      return offsetMap.byteToChar[clamped] ?? lectureScript.length;
    };

    const sentenceStart = mapIndex(highlightPosition.currentSentence?.start);
    const sentenceEnd = mapIndex(highlightPosition.currentSentence?.end);
    const wordStart = mapIndex(highlightPosition.currentWord?.start);
    const wordEnd = mapIndex(highlightPosition.currentWord?.end);

    if (sentenceStart === undefined && wordStart === undefined) {
      container.textContent = lectureScript;
      currentWordRef.current = null;
      return;
    }

    const text = lectureScript;
    const boundaries = new Set<number>([0, text.length]);
    if (sentenceStart !== undefined) boundaries.add(sentenceStart);
    if (sentenceEnd !== undefined) boundaries.add(sentenceEnd);
    if (wordStart !== undefined) boundaries.add(wordStart);
    if (wordEnd !== undefined) boundaries.add(wordEnd);

    const points = Array.from(boundaries).sort((a, b) => a - b);
    const fragment = document.createDocumentFragment();
    currentWordRef.current = null;

    for (let i = 0; i < points.length - 1; i++) {
      const start = points[i];
      const end = points[i + 1];
      if (start === end) continue;
      const slice = text.substring(start, end);

      const isWord = wordStart !== undefined && wordEnd !== undefined && start >= wordStart && end <= wordEnd;
      const isSentence =
        sentenceStart !== undefined &&
        sentenceEnd !== undefined &&
        start >= sentenceStart &&
        end <= sentenceEnd &&
        !isWord;

      if (isWord) {
        const span = document.createElement("span");
        span.className = "word-highlight";
        span.style.backgroundColor = "#fde047";
        span.textContent = slice;
        fragment.appendChild(span);
        currentWordRef.current = span;
      } else if (isSentence) {
        const span = document.createElement("span");
        span.className = "sentence-highlight";
        span.style.backgroundColor = "#fef9c3";
        span.textContent = slice;
        fragment.appendChild(span);
      } else {
        fragment.appendChild(document.createTextNode(slice));
      }
    }

    container.replaceChildren(fragment);
  }, [
    lectureScript,
    isPlaying,
    highlightPosition.currentSentence,
    highlightPosition.currentWord,
    offsetMap,
  ]);

  // Auto-scroll to keep current word visible
  useEffect(() => {
    if (!isPlaying || !currentWordRef.current || !scrollContainerRef.current) return;
    
    const wordEl = currentWordRef.current;
    const scrollContainer = scrollContainerRef.current;
    
    const wordRect = wordEl.getBoundingClientRect();
    const containerRect = scrollContainer.getBoundingClientRect();
    
    const lineHeight = parseFloat(getComputedStyle(wordEl).lineHeight) || 24;
    const isAbove = wordRect.top < containerRect.top;
    const isNearBottom = wordRect.bottom > containerRect.bottom - lineHeight * 2;
    
    if (isAbove || isNearBottom) {
      const currentScrollTop = scrollContainer.scrollTop;
      const wordTopRelativeToContainer = wordRect.top - containerRect.top;
      const targetScrollTop = currentScrollTop + wordTopRelativeToContainer - lineHeight;
      
      scrollContainer.scrollTo({
        top: targetScrollTop,
        behavior: 'smooth',
      });
    }
  }, [highlightPosition.wordIndex, isPlaying]);

  // Handle click to seek
  const handleClick = (e: React.MouseEvent) => {
    if (!onWordClick || wordMarks.length === 0) return;
    
    const container = containerRef.current;
    if (!container) return;
    
    const range = document.caretRangeFromPoint
      ? document.caretRangeFromPoint(e.clientX, e.clientY)
      : null;
    if (!range) return;

    const preRange = document.createRange();
    preRange.setStart(container, 0);
    preRange.setEnd(range.startContainer, range.startOffset);
    const clickedChar = preRange.toString().length;
    
    if (clickedChar < 0) return;
    
    const clickedByte = offsetMap.charToByte[
      Math.min(clickedChar, offsetMap.charToByte.length - 1)
    ];

    // Find which word was clicked
    for (let i = 0; i < wordMarks.length; i++) {
      const mark = wordMarks[i];
      if (clickedByte >= mark.start && clickedByte < mark.end) {
        onWordClick(i);
        break;
      }
    }
  };

  return (
    <div
      ref={containerRef}
      onClick={handleClick}
      className={`lecture-text ${className} cursor-pointer whitespace-pre-wrap leading-relaxed`}
      style={{ 
        maxWidth: '65ch',
        fontSize: '1rem',
        lineHeight: '1.75',
        color: '#334155'
      }}
    >
      {lectureScript}
    </div>
  );
};
