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
  const offsetRef = useRef<number>(0);

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

  const normalizedText = useMemo(() => {
    return lectureScript
      .replace(/\u00a0/g, " ")
      .replace(/[’‘]/g, "'")
      .replace(/[–—]/g, "-");
  }, [lectureScript]);

  const findNearestMatch = useMemo(() => {
    return (value: string, expectedIndex: number, window: number) => {
      if (!value) return null;
      const variants = [
        value,
        value.replace(/\u00a0/g, " ").replace(/[’‘]/g, "'").replace(/[–—]/g, "-"),
      ];
      const texts = [lectureScript, normalizedText];

      let bestIndex: number | null = null;
      let bestDelta = Number.POSITIVE_INFINITY;

      for (const text of texts) {
        for (const v of variants) {
          let start = Math.max(0, expectedIndex - window);
          const end = Math.min(text.length, expectedIndex + window);
          while (start <= end) {
            const found = text.indexOf(v, start);
            if (found === -1 || found > end) break;
            const delta = Math.abs(found - expectedIndex);
            if (delta < bestDelta) {
              bestDelta = delta;
              bestIndex = found;
            }
            start = found + 1;
          }
        }
      }

      return bestIndex;
    };
  }, [lectureScript, normalizedText]);

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
      offsetRef.current = 0;
      return;
    }

    const mapIndex = (idx?: number) => {
      if (idx === undefined) return undefined;
      const clamped = Math.max(0, Math.min(idx, offsetMap.byteLength));
      return offsetMap.byteToChar[clamped] ?? lectureScript.length;
    };

    const rawSentenceStart = mapIndex(highlightPosition.currentSentence?.start);
    const rawSentenceEnd = mapIndex(highlightPosition.currentSentence?.end);
    const rawWordStart = mapIndex(highlightPosition.currentWord?.start);
    const rawWordEnd = mapIndex(highlightPosition.currentWord?.end);

    let sentenceStart = rawSentenceStart;
    let sentenceEnd = rawSentenceEnd;
    let wordStart = rawWordStart;
    let wordEnd = rawWordEnd;

    // Refine offset using current word value if mismatch detected
    if (
      highlightPosition.currentWord &&
      rawWordStart !== undefined &&
      rawWordEnd !== undefined
    ) {
      const expected = rawWordStart + offsetRef.current;
      const expectedEnd = rawWordEnd + offsetRef.current;
      const slice = lectureScript.substring(
        Math.max(0, expected),
        Math.min(lectureScript.length, expectedEnd)
      );

      if (slice !== highlightPosition.currentWord.value) {
        const matchIndex = findNearestMatch(
          highlightPosition.currentWord.value,
          rawWordStart,
          80
        );
        if (matchIndex !== null) {
          offsetRef.current = matchIndex - rawWordStart;
        }
      }
    }

    const offset = offsetRef.current;
    if (sentenceStart !== undefined) sentenceStart += offset;
    if (sentenceEnd !== undefined) sentenceEnd += offset;
    if (wordStart !== undefined) wordStart += offset;
    if (wordEnd !== undefined) wordEnd += offset;

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
    findNearestMatch,
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
    
    const adjustedChar = Math.max(0, clickedChar - offsetRef.current);
    const clickedByte = offsetMap.charToByte[
      Math.min(adjustedChar, offsetMap.charToByte.length - 1)
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
