import { useState, useEffect, useRef, useCallback } from "react";
import { getSectionAudioWithMarks, type SpeechMark } from "../api/courses";

/**
 * Current highlight position during playback.
 * Provides word-level and sentence-level tracking for text highlighting.
 */
export interface HighlightPosition {
  /** Current word being spoken */
  currentWord: SpeechMark | null;
  /** Current sentence being spoken */
  currentSentence: SpeechMark | null;
  /** Index of current word mark */
  wordIndex: number;
  /** Index of current sentence mark */
  sentenceIndex: number;
  /** Current audio time in milliseconds */
  timeMs: number;
}

interface UsePollyAudioProps {
  sectionId: string;
  lectureScript: string | null;
  playbackSpeed: number;
  onError: (error: string) => void;
}

interface UsePollyAudioReturn {
  // State
  isPlaying: boolean;
  isLoading: boolean;
  audioAvailable: boolean;
  speechMarks: SpeechMark[];
  highlightPosition: HighlightPosition;
  audioDuration: number;
  currentTime: number;
  
  // Refs
  audioRef: React.RefObject<HTMLAudioElement>;
  
  // Actions
  play: () => Promise<void>;
  pause: () => void;
  seek: (timeMs: number) => void;
  seekToWord: (wordIndex: number) => void;
  loadAudio: () => Promise<void>;
}

/**
 * Hook for managing Polly TTS audio playback with speech marks.
 * 
 * Provides:
 * - On-demand audio loading from AWS Polly
 * - Word-level and sentence-level speech mark tracking
 * - Real-time highlight position updates for text synchronization
 * - Playback speed support
 */
export const usePollyAudio = ({
  sectionId,
  lectureScript,
  playbackSpeed,
  onError,
}: UsePollyAudioProps): UsePollyAudioReturn => {
  // Audio state
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [audioAvailable, setAudioAvailable] = useState(false);
  const [audioDuration, setAudioDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [markTimeScale, setMarkTimeScale] = useState(1);
  
  // Speech marks state
  const [speechMarks, setSpeechMarks] = useState<SpeechMark[]>([]);
  const [highlightPosition, setHighlightPosition] = useState<HighlightPosition>({
    currentWord: null,
    currentSentence: null,
    wordIndex: -1,
    sentenceIndex: -1,
    timeMs: 0,
  });
  
  // Refs
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioBlobUrlRef = useRef<string | null>(null);
  const wordMarksRef = useRef<SpeechMark[]>([]);
  const sentenceMarksRef = useRef<SpeechMark[]>([]);
  const rafIdRef = useRef<number | null>(null);
  
  // Separate marks by type for efficient lookup
  useEffect(() => {
    wordMarksRef.current = speechMarks.filter(m => m.type === 'word');
    sentenceMarksRef.current = speechMarks.filter(m => m.type === 'sentence');
  }, [speechMarks]);

  // Compute time scale factor to align marks with actual audio duration
  useEffect(() => {
    if (!audioDuration || speechMarks.length === 0) {
      setMarkTimeScale(1);
      return;
    }
    const lastMarkTime = speechMarks[speechMarks.length - 1]?.time || 0;
    if (lastMarkTime > 0) {
      setMarkTimeScale(audioDuration / lastMarkTime);
    } else {
      setMarkTimeScale(1);
    }
  }, [audioDuration, speechMarks]);
  
  // Clean up blob URL on unmount
  useEffect(() => {
    return () => {
      if (audioBlobUrlRef.current) {
        URL.revokeObjectURL(audioBlobUrlRef.current);
      }
    };
  }, []);
  
  // Update playback speed when it changes
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = playbackSpeed;
    }
  }, [playbackSpeed]);
  
  /**
   * Find the current speech mark for a given time.
   * Uses binary search for efficiency with large mark arrays.
   */
  const findMarkAtTime = useCallback((marks: SpeechMark[], timeMs: number): { mark: SpeechMark | null; index: number } => {
    if (marks.length === 0) return { mark: null, index: -1 };
    
    // Binary search for the last mark that starts before or at timeMs
    let left = 0;
    let right = marks.length - 1;
    let result = -1;
    
    while (left <= right) {
      const mid = Math.floor((left + right) / 2);
      if (marks[mid].time <= timeMs) {
        result = mid;
        left = mid + 1;
      } else {
        right = mid - 1;
      }
    }
    
    if (result === -1) return { mark: null, index: -1 };
    
    // Check if we're still within this mark's duration
    // Estimate duration based on next mark or use a default
    const mark = marks[result];
    const nextMark = marks[result + 1];
    const estimatedEndTime = nextMark ? nextMark.time : mark.time + 500; // Default 500ms for last word
    
    if (timeMs <= estimatedEndTime) {
      return { mark, index: result };
    }
    
    return { mark: null, index: -1 };
  }, []);
  
  /**
   * Update highlight position based on current audio time.
   * Called on every time update for smooth tracking.
   */
  const updateHighlightPosition = useCallback((timeMs: number) => {
    // Adjust time to compensate for mark/audio duration drift
    const adjustedTime = markTimeScale !== 0 ? timeMs / markTimeScale : timeMs;
    
    const wordResult = findMarkAtTime(wordMarksRef.current, adjustedTime);
    const sentenceResult = findMarkAtTime(sentenceMarksRef.current, adjustedTime);
    
    setHighlightPosition({
      currentWord: wordResult.mark,
      currentSentence: sentenceResult.mark,
      wordIndex: wordResult.index,
      sentenceIndex: sentenceResult.index,
      timeMs: adjustedTime,
    });
  }, [findMarkAtTime, markTimeScale]);
  
  /**
   * Load audio and speech marks from API.
   */
  const loadAudio = useCallback(async () => {
    if (!sectionId || !lectureScript) {
      console.log("Cannot load audio: missing sectionId or lectureScript");
      return;
    }
    
    if (isLoading || audioAvailable) {
      console.log("Audio already loading or available, skipping load");
      return;
    }
    
    setIsLoading(true);
    console.log(`Loading Polly audio for section ${sectionId}...`);
    
    try {
      const { audioUrl, marks } = await getSectionAudioWithMarks(sectionId);
      
      // Store blob URL
      if (audioBlobUrlRef.current) {
        URL.revokeObjectURL(audioBlobUrlRef.current);
      }
      audioBlobUrlRef.current = audioUrl;
      
      // Set speech marks
      setSpeechMarks(marks);
      
      // Set audio source
      if (audioRef.current) {
        audioRef.current.src = audioUrl;
        audioRef.current.playbackRate = playbackSpeed;
        audioRef.current.load();
      }
      
      setAudioAvailable(true);
      console.log(`✅ Loaded audio (${marks.length} speech marks)`);
      
    } catch (err: any) {
      console.error("Failed to load audio:", err);
      onError(err.message || "Failed to load audio");
    } finally {
      setIsLoading(false);
    }
  }, [sectionId, lectureScript, isLoading, audioAvailable, playbackSpeed, onError]);
  
  /**
   * Start or resume playback.
   */
  const play = useCallback(async () => {
    const audio = audioRef.current;
    if (!audio) {
      console.error("Audio element not found");
      return;
    }
    
    // Load audio if not yet loaded
    if (!audioAvailable && !isLoading) {
      await loadAudio();
      
      // If audio still not available after load attempt, don't try to play
      // (this can happen if lectureScript is null or load failed)
      if (!audioRef.current?.src) {
        console.log("Audio not available after load attempt, skipping play");
        return;
      }
    }
    
    try {
      audio.playbackRate = playbackSpeed;
      // Sync highlight immediately on play
      updateHighlightPosition(audio.currentTime * 1000);
      await audio.play();
      setIsPlaying(true);
    } catch (err: any) {
      console.error("Failed to play audio:", err);
      onError(err.message || "Failed to play audio");
    }
  }, [audioAvailable, isLoading, loadAudio, playbackSpeed, onError, updateHighlightPosition]);
  
  /**
   * Pause playback.
   */
  const pause = useCallback(() => {
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      setIsPlaying(false);
    }
  }, []);
  
  /**
   * Seek to a specific time in milliseconds.
   */
  const seek = useCallback((timeMs: number) => {
    const audio = audioRef.current;
    if (audio) {
      audio.currentTime = timeMs / 1000;
      updateHighlightPosition(timeMs);
    }
  }, [updateHighlightPosition]);
  
  /**
   * Seek to a specific word by index.
   */
  const seekToWord = useCallback((wordIndex: number) => {
    const wordMark = wordMarksRef.current[wordIndex];
    if (wordMark) {
      seek(wordMark.time);
    }
  }, [seek]);
  
  // Set up audio event handlers
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    
    const handleTimeUpdate = () => {
      const timeMs = audio.currentTime * 1000;
      setCurrentTime(timeMs);
      updateHighlightPosition(timeMs);
    };
    
    const handleLoadedMetadata = () => {
      setAudioDuration(audio.duration * 1000);
      audio.playbackRate = playbackSpeed;
    };
    
    const handleEnded = () => {
      setIsPlaying(false);
      setHighlightPosition({
        currentWord: null,
        currentSentence: null,
        wordIndex: -1,
        sentenceIndex: -1,
        timeMs: 0,
      });
    };
    
    const handlePlay = () => {
      setIsPlaying(true);
    };
    
    const handlePause = () => {
      setIsPlaying(false);
    };
    
    const handleError = (e: Event) => {
      console.error("Audio error:", e);
      setIsPlaying(false);
    };
    
    audio.addEventListener('timeupdate', handleTimeUpdate);
    audio.addEventListener('loadedmetadata', handleLoadedMetadata);
    audio.addEventListener('ended', handleEnded);
    audio.addEventListener('play', handlePlay);
    audio.addEventListener('pause', handlePause);
    audio.addEventListener('error', handleError);
    
    return () => {
      audio.removeEventListener('timeupdate', handleTimeUpdate);
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
      audio.removeEventListener('ended', handleEnded);
      audio.removeEventListener('play', handlePlay);
      audio.removeEventListener('pause', handlePause);
      audio.removeEventListener('error', handleError);
    };
  }, [playbackSpeed, updateHighlightPosition]);

  // Fallback: keep highlight in sync even if timeupdate is throttled
  useEffect(() => {
    if (!isPlaying) {
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
      return;
    }

    const tick = () => {
      const audio = audioRef.current;
      if (audio) {
        updateHighlightPosition(audio.currentTime * 1000);
      }
      rafIdRef.current = requestAnimationFrame(tick);
    };

    rafIdRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
    };
  }, [isPlaying, updateHighlightPosition]);
  
  return {
    // State
    isPlaying,
    isLoading,
    audioAvailable,
    speechMarks,
    highlightPosition,
    audioDuration,
    currentTime,
    
    // Refs
    audioRef,
    
    // Actions
    play,
    pause,
    seek,
    seekToWord,
    loadAudio,
  };
};
