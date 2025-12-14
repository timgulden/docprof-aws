import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Play, Pause, CheckCircle, ArrowLeft, Hand } from "lucide-react";
import { getSectionLecture, getGenerationStatus, completeSection, getSectionLectureMetadata, type ChunkMetadata } from "../../api/courses";
import { sendChatMessage, streamChatMessage, generateAudioForText } from "../../api/chat";
import type { BackendChatResponse } from "../../types/api";
import { getCurrentUser, updatePlaybackSpeed } from "../../api/auth";
// SectionQAMode removed - using inline Q&A now
import { PDFViewer } from "../pdf/PDFViewer";
import { PDFViewerEmpty } from "../pdf/PDFViewerEmpty";
import { usePdfViewer } from "../../hooks/usePdfViewer";
import { useSectionAudio } from "../../hooks/useSectionAudio";
import type { SourceCitation } from "../../types/chat";
import { API_URL } from "../../api/client";
import { FigureViewerItem } from "./FigureViewerItem";
import { QACard } from "./QACard";
import { GenerationProgress } from "./GenerationProgress";

interface SectionPlayerProps {
  sectionId: string;
  sectionTitle?: string;
  courseId?: string;
  onComplete?: () => void;
}

export const SectionPlayer = ({ sectionId, sectionTitle, courseId: propCourseId, onComplete }: SectionPlayerProps) => {
  const navigate = useNavigate();
  const { courseId: paramCourseId } = useParams<{ courseId: string }>();
  const courseId = propCourseId || paramCourseId; // Use prop first, then param
  const [lectureScript, setLectureScript] = useState<string | null>(null);
  const [lectureFigures, setLectureFigures] = useState<Array<{
    figure_id: string;
    chunk_id: string;
    caption: string;
    description: string;
    page: number;
    book_id: string;
    chapter_number?: number;
    similarity: number;
    explanation?: string;
  }>>([]);
  // Track preloaded figure images to prevent duplicate fetches
  const preloadedFigureImages = useRef<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Inline Q&A state
  interface QAExchange {
    question: string;
    answer: string;
    sources: SourceCitation[];
    audioUrl?: string;  // Audio URL for TTS playback
  }
  
  interface QACard {
    paragraphIndex: number;
    exchanges: QAExchange[];  // Array of Q&A exchanges (unlimited)
  }
  
  // Store audio URLs for Q&A answers (cardId -> audioUrl)
  const qaAudioUrlsRef = useRef<Map<string, string>>(new Map());
  
  const [activeQuestionIndex, setActiveQuestionIndex] = useState<number | null>(null);
  const [qaCards, setQACards] = useState<QACard[]>([]);
  const [isLoadingAnswer, setIsLoadingAnswer] = useState(false);
  const [isLoadingFollowUp, setIsLoadingFollowUp] = useState<string | null>(null);  // Now uses cardId string
  // Track abort controllers for streaming requests
  const streamingAbortControllers = useRef<Map<string, AbortController>>(new Map());
  
  // Helper function to load Q&A history from API response
  const loadQAHistory = (qaHistory: Array<{
    chunk_index: number;
    question: string;
    answer: string;
    sources?: Array<{
      citation_id: string;
      chunk_id: string;
      chunk_type: string;
      book_id: string;
      book_title: string;
      chapter_number?: number;
      chapter_title?: string;
      page_start?: number;
      page_end?: number;
      target_page?: number;
      content: string;
      score?: number;
    }>;
    created_at: string;
  }>) => {
    if (!qaHistory || qaHistory.length === 0) return;
    
    // Group Q&A by chunk_index
    const qaByChunk = new Map<number, QAExchange[]>();
    for (const qa of qaHistory) {
      const chunkIdx = qa.chunk_index;
      if (!qaByChunk.has(chunkIdx)) {
        qaByChunk.set(chunkIdx, []);
      }
      // Convert sources from backend format to frontend format
      const sources: SourceCitation[] = (qa.sources || []).map((src: any) => ({
        citationId: src.citation_id || "",
        chunkId: src.chunk_id || "",
        chunkType: src.chunk_type || "2page",
        bookId: src.book_id || "",
        bookTitle: src.book_title || "",
        chapterNumber: src.chapter_number,
        chapterTitle: src.chapter_title,
        pageStart: src.page_start,
        pageEnd: src.page_end,
        targetPage: src.target_page,
        content: src.content || "",
        score: src.score,
      }));
      qaByChunk.get(chunkIdx)!.push({
        question: qa.question,
        answer: qa.answer,
        sources: sources,
      });
    }
    
    // Convert to QACard format
    const loadedQACards: QACard[] = Array.from(qaByChunk.entries()).map(([chunkIdx, exchanges]) => ({
      paragraphIndex: chunkIdx,
      exchanges: exchanges,
    }));
    setQACards(loadedQACards);
    console.log(`✅ Loaded ${qaHistory.length} Q&A exchanges into ${loadedQACards.length} Q&A cards`);
  };
  
  // PDF reader state (for citations)
  const pdfViewer = usePdfViewer();
  const [estimatedMinutes, setEstimatedMinutes] = useState(0);
  const [generationProgress, setGenerationProgress] = useState<string>("");
  const [generationStartTime, setGenerationStartTime] = useState<number | null>(null);
  const [progressPercent, setProgressPercent] = useState<number>(0);
  const [currentStep, setCurrentStep] = useState<string>("");
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1.5); // Will be loaded from user profile
  const [chunkMetadata, setChunkMetadata] = useState<ChunkMetadata[] | null>(null);
  
  // Use audio hook for all audio playback logic
  const {
    isPlaying,
    isLoadingChunk,
    audioAvailable,
    audioBlobUrl,
    currentChunkIndex,
    audioRef,
    nextAudioRef,
    handlePlayPause,
    handleChunkClick,
    onPlay,
    onPause,
    onTimeUpdate,
    onEnded,
    onError,
    onLoadedMetadata,
  } = useSectionAudio({
    sectionId,
    chunkMetadata,
    playbackSpeed,
    setCurrentChunkIndex: (index) => {
      // This is handled internally by the hook
    },
    setError,
  });
  
  // Debug logging ref - only log on significant changes (every 5 seconds)
  // Reduce console spam from elapsed time counter (updates every 1 second)
  const lastLogTimeRef = useRef<number>(0);
  
  // Refs for each chunk paragraph for scrolling and interaction
  const chunkRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  
  // Request deduplication: track in-flight getSectionLecture requests
  const getSectionLecturePromiseRef = useRef<Promise<any> | null>(null);
  
  // Helper function to set figures and preload their images
  const setFiguresAndPreload = useCallback((figures: Array<any>) => {
    setLectureFigures(figures);
    
    // Preload figure images immediately
    if (figures && figures.length > 0) {
      figures.forEach((figure: any) => {
        const imageUrl = `${API_URL}/mna-expert/figures/${figure.figure_id}/image`;
        if (!preloadedFigureImages.current.has(imageUrl)) {
          preloadedFigureImages.current.add(imageUrl);
          // Preload image in background
          const img = new Image();
          img.src = imageUrl;
          console.log(`Preloading figure image: ${figure.figure_id}`);
        }
      });
    }
  }, []);

  // Load user's playback speed preference on mount
  useEffect(() => {
    const loadPlaybackSpeed = async () => {
      try {
        const user = await getCurrentUser();
        if (user.playbackSpeed) {
          setPlaybackSpeed(user.playbackSpeed);
        }
      } catch (error) {
        console.error("Failed to load user playback speed preference:", error);
        // Keep default 1.5x if loading fails
      }
    };
    loadPlaybackSpeed();
  }, []);

  // Load chunk metadata when lecture script is available
  useEffect(() => {
    if (!lectureScript) {
      setChunkMetadata(null);
      return;
    }

    const loadMetadata = async () => {
      try {
        console.log("Loading lecture metadata for highlighting...");
        const metadata = await getSectionLectureMetadata(sectionId);
        console.log(`✅ Loaded ${metadata.chunks.length} chunks for highlighting`);
        console.log(`Chunk metadata sample:`, metadata.chunks.slice(0, 2).map(c => ({
          text: c.text.substring(0, 50) + '...',
          start_proportion: c.start_proportion,
          end_proportion: c.end_proportion
        })));
        setChunkMetadata(metadata.chunks);
        // currentChunkIndex is managed by the hook
      } catch (error) {
        console.error("❌ Failed to load lecture metadata:", error);
        // If metadata fails, we can still display the lecture without highlighting
        setChunkMetadata(null);
      }
    };

    loadMetadata();
  }, [lectureScript, sectionId]);

  // Set up click handlers for figure links when lecture content is rendered
  useEffect(() => {
    if (!chunkMetadata || chunkMetadata.length === 0) return;
    
    // Helper function to scroll to figure
    const scrollToFigure = (figureId: string) => {
      const figureElement = document.getElementById(`figure-${figureId}`);
      if (figureElement) {
        figureElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        // Highlight the figure briefly
        figureElement.style.transition = 'box-shadow 0.3s';
        figureElement.style.boxShadow = '0 0 0 3px rgba(37, 99, 235, 0.5)';
        setTimeout(() => {
          figureElement.style.boxShadow = '';
        }, 2000);
      }
    };
    
    // Wait for DOM to be ready
    const timeoutId = setTimeout(() => {
      document.querySelectorAll('a.figure-link').forEach((link) => {
        // Remove existing listeners to avoid duplicates
        const newLink = link.cloneNode(true) as HTMLAnchorElement;
        link.parentNode?.replaceChild(newLink, link);
        
            newLink.addEventListener('click', (e) => {
              e.preventDefault();
              const figureId = newLink.getAttribute('data-figure-id');
              if (figureId) {
                // Close PDF viewer if open to show figure sidebar
                if (pdfViewer.isOpen) {
                  pdfViewer.closePdf();
                }
                // Ensure figure sidebar is visible by checking if figures exist
                // The sidebar should already be visible if lectureFigures.length > 0
                // Wait a moment for layout to adjust, then scroll to figure
                setTimeout(() => {
                  scrollToFigure(figureId);
                }, pdfViewer.isOpen ? 150 : 50);
              }
            });
      });
    }, 200);
    
    return () => clearTimeout(timeoutId);
  }, [chunkMetadata, pdfViewer, lectureFigures]);

  const handleBack = () => {
    // IMPORTANT: Stop all audio/generation before navigating away
    // This prevents backend from continuing to generate and blocking other requests
    
    // Stop audio playback
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.src = ''; // Clear src to stop backend stream
      audio.load();
    }
    
    // Audio abort controllers are now managed by the hook
    
    // Since SectionPlayer is rendered inside CourseDashboard (not a separate route),
    // we should use the onComplete callback to go back to the dashboard
    if (onComplete) {
      onComplete();
    } else if (courseId) {
      // Fallback: navigate to course dashboard
      navigate(`/courses/${courseId}`);
    } else {
      // Last resort: go to courses list
      navigate("/courses");
    }
  };

  useEffect(() => {
    const loadLecture = async () => {
      try {
        // Deduplicate getSectionLecture requests - reuse in-flight promise
        if (!getSectionLecturePromiseRef.current) {
          getSectionLecturePromiseRef.current = getSectionLecture(sectionId);
        }
        
        // First, check if lecture already exists
        const data = await getSectionLecturePromiseRef.current;
        getSectionLecturePromiseRef.current = null; // Clear after use
        
        // If we get here, lecture exists and is ready
        setLectureScript(data.lectureScript);
        setEstimatedMinutes(data.estimatedMinutes);
        console.log("getSectionLecture response:", { figures: data.figures, figuresCount: data.figures?.length || 0, qaHistory: data.qaHistory?.length || 0 });
        setFiguresAndPreload(data.figures || []);
        
        // Load Q&A history if available
        if (data.qaHistory) {
          loadQAHistory(data.qaHistory);
        }
        
        setGenerationProgress("");
        setGenerationStartTime(null);
        setLoading(false);
        
        // Don't check audio on load - only check when user clicks play
        // This prevents errors for existing lectures without audio
        
        return; // Lecture exists, we're done
      } catch (err: any) {
        // Handle 202 Accepted (generation in progress) - start polling
        if (err.response?.status === 202 || err.isGenerationInProgress) {
          setLoading(true);
          setError(null);
          setGenerationStartTime(Date.now());
          setGenerationProgress("Lecture generation in progress...");
          // Polling will be handled by the useEffect below
          return;
        }
        
        // Lecture doesn't exist yet or error occurred
        if (err.response?.status === 404) {
          // Lecture doesn't exist - start generation and polling
          setLoading(true);
          setError(null);
          setGenerationStartTime(Date.now());
          setGenerationProgress("Starting lecture generation...");
          
          // Fire off generation request (don't wait for it)
          // The polling will track progress
          // Deduplicate: reuse existing promise if available
          if (!getSectionLecturePromiseRef.current) {
            getSectionLecturePromiseRef.current = getSectionLecture(sectionId);
          }
          getSectionLecturePromiseRef.current.catch((genErr: any) => {
            // Handle 202 (generation in progress) - this is fine
            if (genErr.response?.status === 202 || genErr.isGenerationInProgress) {
              // Generation started - polling will handle it
              return;
            }
            
            // Generation request failed with real error
            console.error("Failed to start lecture generation:", genErr);
            setGenerationProgress("");
            setGenerationStartTime(null);
            setLoading(false);
            
            if (genErr.code === 'ECONNABORTED' || genErr.message?.includes('timeout')) {
              setError("Lecture generation is taking longer than expected. Please try again - the lecture may have been generated.");
            } else if (genErr.response?.data?.detail) {
              // Ensure detail is a string, not an object
              const detail = genErr.response.data.detail;
              setError(typeof detail === 'string' ? detail : detail?.message || "Failed to start lecture generation");
            } else if (genErr.message) {
              setError(genErr.message);
            } else {
              setError("Failed to start lecture generation. Please check your connection and try again.");
            }
          });
          // Note: We don't wait for generation - polling will handle progress updates
        } else {
          // Some other error - check if it's a timeout during generation
          console.error("Failed to load lecture:", err);
          
          // If it's a timeout and we might be generating, treat as "generation in progress"
          // This prevents stopping polling when /lecture times out but status checks work
          if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
            // Timeout could mean generation is in progress - start polling to check
            setLoading(true);
            setError(null);
            setGenerationStartTime(Date.now());
            setGenerationProgress("Checking generation status...");
            // Polling will verify if generation is actually running
            return;
          }
          
          // Real error - stop loading
          setGenerationProgress("");
          setGenerationStartTime(null);
          setLoading(false);
          
          // Ensure error is a string, not an object
          if (err.response?.data?.detail) {
            const detail = err.response.data.detail;
            setError(typeof detail === 'string' ? detail : detail?.message || "Failed to load lecture");
          } else if (err.message) {
            setError(err.message);
          } else {
            setError("Failed to load lecture. Please check your connection and try again.");
          }
        }
      }
    };

    loadLecture();
  }, [sectionId]);

  // Update elapsed time every second
  useEffect(() => {
    if (!loading || !generationStartTime) {
      setElapsedSeconds(0);
      return;
    }

    const elapsedInterval = setInterval(() => {
      const elapsed = (Date.now() - generationStartTime) / 1000;
      setElapsedSeconds(Math.floor(elapsed));
    }, 1000);

    return () => clearInterval(elapsedInterval);
  }, [loading, generationStartTime]);

  // Poll for generation status during loading
  useEffect(() => {
    if (!loading) return;

    let pollInterval: ReturnType<typeof setInterval> | null = null;
    let checkCompleteInterval: ReturnType<typeof setInterval> | null = null;

    // Track consecutive errors to prevent infinite error loops
    let consecutiveErrors = 0;
    const MAX_CONSECUTIVE_ERRORS = 5;

    const pollStatus = async () => {
      try {
        const status = await getGenerationStatus(sectionId);
        
        // Reset error counter on success
        consecutiveErrors = 0;
        
        // Always update UI with status (even if "not_started" - generation might be starting)
        setProgressPercent(status.progress_percent);
        setCurrentStep(status.current_step);
        
        // If complete, try to load the lecture
        // But only if we're actually at 100% and phase is complete
        // Don't stop if we're still generating (progress < 100%)
        if (status.phase === "complete" && status.progress_percent >= 100) {
          // Stop polling and try to load
          if (pollInterval) clearInterval(pollInterval);
          if (checkCompleteInterval) clearInterval(checkCompleteInterval);
          
          // Small delay to ensure delivery is saved
          setTimeout(async () => {
            try {
              // Deduplicate: reuse existing promise if available
              if (!getSectionLecturePromiseRef.current) {
                getSectionLecturePromiseRef.current = getSectionLecture(sectionId);
              }
              const data = await getSectionLecturePromiseRef.current;
              getSectionLecturePromiseRef.current = null; // Clear after use
              setLectureScript(data.lectureScript);
              setEstimatedMinutes(data.estimatedMinutes);
              setFiguresAndPreload(data.figures || []);
              
              // Load Q&A history if available
              if (data.qaHistory) {
                loadQAHistory(data.qaHistory);
              }
              
              setGenerationProgress("");
              setGenerationStartTime(null);
              setLoading(false);
              // Don't check audio - only when user clicks play
            } catch (err: any) {
              console.error("Failed to load completed lecture:", err);
              setError("Lecture generation completed but failed to load. Please refresh.");
              setLoading(false);
            }
          }, 1000);
        }
      } catch (err: any) {
        consecutiveErrors++;
        
        // If status endpoint fails, continue with time-based progress
        console.error(`Failed to poll generation status (attempt ${consecutiveErrors}/${MAX_CONSECUTIVE_ERRORS}):`, err);
        console.error("Status poll error details:", {
          message: err.message,
          response: err.response?.data,
          status: err.response?.status,
          url: err.config?.url,
          code: err.code,
        });
        
        // After too many consecutive errors, show warning but keep polling
        if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
          console.warn(`Polling failed ${consecutiveErrors} times in a row. Generation may have stalled or network issues.`);
          // Don't stop polling - generation might still be running
          // Just log the issue and continue
        }
        
        // Don't update UI on error - keep showing last known status
        // But log the error so we can debug
      }
    };

    // Start polling immediately, then every 5 seconds (reduces backend load while still responsive)
    pollStatus();
    pollInterval = setInterval(() => {
      // Double-check that we should still be polling
      if (!loading) {
        if (pollInterval) clearInterval(pollInterval);
        if (checkCompleteInterval) clearInterval(checkCompleteInterval);
        return;
      }
      pollStatus();
    }, 5000);

    // Also check if lecture is ready every 10 seconds (in case status endpoint doesn't work)
    // This is a fallback mechanism, not primary polling
    // NOTE: This can cause connection pool exhaustion if too many concurrent requests
    // Consider removing or increasing interval if issues persist
    checkCompleteInterval = setInterval(async () => {
      // Double-check that we should still be checking
      if (!loading) {
        if (pollInterval) clearInterval(pollInterval);
        if (checkCompleteInterval) clearInterval(checkCompleteInterval);
        return;
      }
      
          try {
            // Deduplicate: reuse existing promise if available
            if (!getSectionLecturePromiseRef.current) {
              getSectionLecturePromiseRef.current = getSectionLecture(sectionId);
            }
            const data = await getSectionLecturePromiseRef.current;
            getSectionLecturePromiseRef.current = null; // Clear after use
            // If we get here, lecture is ready
            setLectureScript(data.lectureScript);
            setEstimatedMinutes(data.estimatedMinutes);
            setLectureFigures(data.figures || []);
            
            // Load Q&A history if available
            if (data.qaHistory) {
              loadQAHistory(data.qaHistory);
            }
            
            setGenerationProgress("");
            setGenerationStartTime(null);
            setLoading(false);
            // Don't check audio - only when user clicks play
            if (pollInterval) clearInterval(pollInterval);
            if (checkCompleteInterval) clearInterval(checkCompleteInterval);
          } catch (err: any) {
        // Handle 202 Accepted (generation in progress) - this is expected, just continue polling
        if (err.response?.status === 202 || err.isGenerationInProgress) {
          // Generation is in progress - this is fine, just continue polling
          // Don't log this as an error since it's expected behavior
          return;
        }
        // Handle timeout errors - these might indicate connection pool exhaustion
        if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
          console.warn("Lecture check timed out - may indicate connection pool exhaustion. Continuing polling...");
          // Continue polling - don't stop
          return;
        }
        // Still generating (404) or server error - continue polling for 404, log for others
        if (err.response?.status === 404) {
          // Expected - lecture not ready yet, continue polling
          return;
        }
        if (err.response?.status !== 500) {
          // Only log non-expected errors (not 202, 404, or 500)
          console.error("Error checking lecture:", err);
        }
      }
    }, 15000); // Increased from 10s to 15s to reduce concurrent request load

    return () => {
      if (pollInterval) clearInterval(pollInterval);
      if (checkCompleteInterval) clearInterval(checkCompleteInterval);
    };
  }, [loading, sectionId]);

  // Check if audio is available for this section
  // Audio availability is now managed by the hook


  // Auto-play logic is now handled by the hook

  // Cleanup on unmount: stop audio, cancel generation, revoke blob URLs
  // IMPORTANT: Only run cleanup on actual unmount, not when dependencies change
  useEffect(() => {
    // Store current audioBlobUrl in closure for cleanup
    const currentBlobUrl = audioBlobUrl;
    
    return () => {
      // Stop audio playback
      const audio = audioRef.current;
      if (audio) {
        audio.pause();
        audio.src = '';
        audio.load(); // Reset audio element
      }
      
      // Audio abort controllers are now managed by the hook
      
      // Cancel any ongoing Q&A streaming
      streamingAbortControllers.current.forEach((controller, id) => {
        console.log(`Cancelling Q&A stream on unmount: ${id}`);
        controller.abort();
      });
      streamingAbortControllers.current.clear();
      
      // Revoke blob URLs to free memory (use closure value)
      if (currentBlobUrl && currentBlobUrl.startsWith('blob:')) {
        URL.revokeObjectURL(currentBlobUrl);
      }
    };
  }, []); // Empty dependency array - only run cleanup on unmount

  // Audio chunk switching is now handled by useSectionAudio hook's onEnded handler

  // Auto-scroll to keep current chunk visible when it extends below viewport
  useEffect(() => {
    if (currentChunkIndex === null || !chunkMetadata || currentChunkIndex >= chunkMetadata.length) {
      return;
    }
    const chunkElement = chunkRefs.current.get(currentChunkIndex);
    if (!chunkElement) {
      return;
    }

    // Find the scrollable container (the main element with overflow-y-auto)
    const scrollContainer = chunkElement.closest('.overflow-y-auto') as HTMLElement;
    if (!scrollContainer) {
      return;
    }

    // Get viewport and element positions
    const containerRect = scrollContainer.getBoundingClientRect();
    const elementRect = chunkElement.getBoundingClientRect();
    
    // Check if chunk extends below the viewport bottom
    const chunkBottom = elementRect.bottom;
    const viewportBottom = containerRect.bottom;
    
    // If chunk extends below viewport, scroll it to the top
    if (chunkBottom > viewportBottom) {
      // Calculate the scroll position to place chunk at top of viewport
      const scrollTop = scrollContainer.scrollTop;
      const elementTopRelativeToContainer = elementRect.top - containerRect.top + scrollTop;
      
      // Scroll to position chunk at top (with a small offset for padding)
      scrollContainer.scrollTo({
        top: elementTopRelativeToContainer - 20, // 20px offset for padding
        behavior: 'smooth'
      });
    }
  }, [currentChunkIndex, chunkMetadata]);

  // handleChunkClick and handlePlayPause are now provided by useSectionAudio hook
  useEffect(() => {
    if (currentChunkIndex === null || !chunkMetadata || currentChunkIndex >= chunkMetadata.length) {
      return;
    }

    const chunkElement = chunkRefs.current.get(currentChunkIndex);
    if (!chunkElement) {
      return;
    }

    // Find the scrollable container (the main element with overflow-y-auto)
    const scrollContainer = chunkElement.closest('.overflow-y-auto') as HTMLElement;
    if (!scrollContainer) {
      return;
    }

    // Get viewport and element positions
    const containerRect = scrollContainer.getBoundingClientRect();
    const elementRect = chunkElement.getBoundingClientRect();
    
    // Check if chunk extends below the viewport bottom
    const chunkBottom = elementRect.bottom;
    const viewportBottom = containerRect.bottom;
    
    // If chunk extends below viewport, scroll it to the top
    if (chunkBottom > viewportBottom) {
      // Calculate the scroll position to place chunk at top of viewport
      const scrollTop = scrollContainer.scrollTop;
      const elementTopRelativeToContainer = elementRect.top - containerRect.top + scrollTop;
      
      // Scroll to position chunk at top (with a small offset for padding)
      scrollContainer.scrollTo({
        top: elementTopRelativeToContainer - 20, // 20px offset for padding
        behavior: 'smooth'
      });
    }
  }, [currentChunkIndex, chunkMetadata]);

  // Auto-scroll to keep current chunk visible when it extends below viewport
  useEffect(() => {
    if (currentChunkIndex === null || !chunkMetadata || currentChunkIndex >= chunkMetadata.length) {
      return;
    }

    const chunkElement = chunkRefs.current.get(currentChunkIndex);
    if (!chunkElement) {
      return;
    }

    // Find the scrollable container (the main element with overflow-y-auto)
    const scrollContainer = chunkElement.closest('.overflow-y-auto') as HTMLElement;
    if (!scrollContainer) {
      return;
    }

    // Get viewport and element positions
    const containerRect = scrollContainer.getBoundingClientRect();
    const elementRect = chunkElement.getBoundingClientRect();
    
    // Check if chunk extends below the viewport bottom
    const chunkBottom = elementRect.bottom;
    const viewportBottom = containerRect.bottom;
    
    // If chunk extends below viewport, scroll it to the top
    if (chunkBottom > viewportBottom) {
      // Calculate the scroll position to place chunk at top of viewport
      const scrollTop = scrollContainer.scrollTop;
      const elementTopRelativeToContainer = elementRect.top - containerRect.top + scrollTop;
      
      // Scroll to position chunk at top (with a small offset for padding)
      scrollContainer.scrollTo({
        top: elementTopRelativeToContainer - 20, // 20px offset for padding
        behavior: 'smooth'
      });
    }
  }, [currentChunkIndex, chunkMetadata]);

  // handleChunkClick and handlePlayPause are now provided by useSectionAudio hook

  // Inline Q&A Handlers
  const handleRaiseHand = (paragraphIndex: number) => {
    // Pause audio if playing
    if (isPlaying) {
      const audio = audioRef.current;
      if (audio) {
        audio.pause();
        // isPlaying is managed by the hook
      }
    }
    
    // Check if Q&A card already exists at this paragraph
    const existingCard = qaCards.find(card => card.paragraphIndex === paragraphIndex);
    if (existingCard) {
      // Just scroll to existing card, don't create new input
      const element = document.getElementById(`qa-card-${paragraphIndex}`);
      element?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }
    
    // Set active question input at this paragraph
    setActiveQuestionIndex(paragraphIndex);
  };

  // Helper to scroll Resume Lecture button to be visible in lower third of viewport
  const scrollToResumeButton = (paragraphIndex: number, cardIndex: number) => {
    setTimeout(() => {
      const buttonId = paragraphIndex === chunkMetadata?.length 
        ? `resume-button-end-${cardIndex}`
        : `resume-button-${paragraphIndex}-${cardIndex}`;
      const button = document.getElementById(buttonId);
      
      if (button) {
        const viewportHeight = window.innerHeight;
        const buttonRect = button.getBoundingClientRect();
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        
        // Position button at 75% down the viewport (leaving 25% below it)
        // This ensures the button is clearly visible with plenty of space
        const targetPosition = viewportHeight * 0.75;
        const targetScrollTop = scrollTop + buttonRect.top - targetPosition;
        
        window.scrollTo({
          top: targetScrollTop,
          behavior: 'smooth'
        });
      }
    }, 100); // Small delay to ensure DOM is updated
  };

  const handleSubmitQuestion = async (paragraphIndex: number, question: string) => {
    if (!question.trim()) return;
    
    setIsLoadingAnswer(true);
    setError(null);
    
    try {
      // Get lecture context
      const deliveredText = chunkMetadata
        ?.slice(0, paragraphIndex)
        .map(c => c.text)
        .join('\n\n') || '';
      
      const remainingText = chunkMetadata
        ?.slice(paragraphIndex)
        .map(c => c.text)
        .join('\n\n') || '';
      
      // Include figure information in context
      const figuresContext = lectureFigures && lectureFigures.length > 0
        ? `\n\n=== FIGURES SHOWN IN LECTURE ===
(Figures that have been displayed or will be displayed in this lecture)
${lectureFigures.map((fig, idx) => 
  `Figure ${idx + 1}: ${fig.caption || 'Untitled Figure'}
  - Description: ${fig.description || 'No description available'}
  - Page: ${fig.page}
  ${fig.explanation ? `- Explanation: ${fig.explanation}` : ''}`
).join('\n\n')}`
        : '';
      
      // Debug logging
      console.log('Submitting question to API:', { 
        question, 
        paragraphIndex,
        totalChunks: chunkMetadata?.length || 0,
        deliveredLength: deliveredText.length,
        remainingLength: remainingText.length,
        figuresCount: lectureFigures?.length || 0,
        deliveredPreview: deliveredText.substring(0, 100) + '...',
        remainingPreview: remainingText.substring(0, 100) + '...'
      });
      
      // Build lecture context for chat endpoint
      const lectureContext = `
You are continuing a lecture that was paused when a student raised their hand to ask a question.

IMPORTANT: Get straight to the answer. NO pleasantries like "Great question!" or "Good observation!" - just answer directly.

=== LECTURE DELIVERED SO FAR ===
(What the student has already heard)
${deliveredText || "(Nothing delivered yet - student paused at the very beginning)"}

=== LECTURE STILL TO COME ===
(What was about to be covered when student raised hand)
${remainingText || "(No remaining content - student is at the end of the lecture)"}
${figuresContext}

When answering, maintain the same conversational style as the lecture. If asked about future content, reference what's in "LECTURE STILL TO COME". If asked about figures, reference the figures shown in the lecture. Be concise and use numbered citations [1], [2] when referencing textbook material.
`.trim();
      
      // Don't create card yet - wait for first chunk to arrive
      const cardId = `${paragraphIndex}-${qaCards.length}`;
      let cardCreated = false;
      let firstChunkReceived = false;
      
      // Audio streaming setup - accumulate chunks
      // We'll wait for all chunks before creating the blob URL to avoid restart issues
      let audioChunks: Uint8Array[] = [];
      let audioUrl: string | null = null;
      
      // Cancel any existing streaming for this card
      const existingController = streamingAbortControllers.current.get(cardId);
      if (existingController) {
        existingController.abort();
      }
      
      // Create abort controller for this stream
      const abortController = new AbortController();
      streamingAbortControllers.current.set(cardId, abortController);
      
      // Try streaming first, fallback to regular endpoint if not available
      try {
        await streamChatMessage(
          {
            message: question,
            context: lectureContext,
            ephemeral: true, // Don't create or persist session for lecture Q&A
            sectionId: sectionId, // Store Q&A tagged with section
            chunkIndex: paragraphIndex, // Store Q&A tagged with chunk/paragraph
          },
          // onChunk - update streaming answer as chunks arrive
          (chunk: string) => {
            // Create card on first chunk
            if (!firstChunkReceived) {
              firstChunkReceived = true;
              setIsLoadingAnswer(false); // Hide loading state once answer starts
              
              // Create the card now with the first chunk
              const newCard: QACard = {
                paragraphIndex,
                exchanges: [{
                  question,
                  answer: chunk, // Start with first chunk
                  sources: []
                }]
              };
              setQACards(prevCards => [...prevCards, newCard]);
              cardCreated = true;
              return;
            }
            
            // Update existing card with additional chunks
            setQACards(prevCards => {
              const updatedCards = [...prevCards];
              // Find the card we created (should be the last one)
              const cardIndex = updatedCards.length - 1;
              if (cardIndex >= 0 && updatedCards[cardIndex].paragraphIndex === paragraphIndex) {
                const currentAnswer = updatedCards[cardIndex].exchanges[0]?.answer || '';
                updatedCards[cardIndex] = {
                  ...updatedCards[cardIndex],
                  exchanges: [{
                    ...updatedCards[cardIndex].exchanges[0],
                    answer: currentAnswer + chunk
                  }]
                };
              }
              return updatedCards;
            });
          },
          // onComplete - finalize answer with sources
          (response: BackendChatResponse) => {
            console.log('✅ Stream complete, finalizing answer');
            
            // Extract answer and sources from response
            if (!response.messages || response.messages.length === 0) {
              throw new Error('Invalid response from chat API - no messages');
            }
            
            const lastMessage = response.messages[response.messages.length - 1];
            
            // If card wasn't created yet (no chunks received), create it now with full answer
            if (!cardCreated) {
              setIsLoadingAnswer(false);
              const newCard: QACard = {
                paragraphIndex,
                exchanges: [{
                  question,
                  answer: lastMessage.content,
                  sources: lastMessage.sources || []
                }]
              };
              setQACards(prevCards => {
                const updated = [...prevCards, newCard];
                // Scroll to the new card after it's added
                setTimeout(() => {
                  scrollToResumeButton(paragraphIndex, updated.length - 1);
                }, 100);
                return updated;
              });
            } else {
              // Update existing card with final answer and sources
              setQACards(prev => {
                const updated = [...prev];
                const cardIndex = updated.findIndex(c => 
                  c.paragraphIndex === paragraphIndex && 
                  c.exchanges.length === 1 && 
                  c.exchanges[0].question === question
                );
                if (cardIndex >= 0) {
                  updated[cardIndex] = {
                    ...updated[cardIndex],
                    exchanges: [{
                      question,
                      answer: lastMessage.content,
                      sources: lastMessage.sources || []
                    }]
                  };
                  // Scroll to the card after it's updated
                  setTimeout(() => {
                    scrollToResumeButton(paragraphIndex, cardIndex);
                  }, 100);
                }
                return updated;
              });
            }
            
            // Finalize audio streaming - create blob URL from all accumulated chunks
            if (audioChunks.length > 0) {
              const combined = new Uint8Array(audioChunks.reduce((acc, chunk) => acc + chunk.length, 0));
              let offset = 0;
              for (const chunk of audioChunks) {
                combined.set(chunk, offset);
                offset += chunk.length;
              }
              const audioBlob = new Blob([combined], { type: 'audio/mpeg' });
              audioUrl = URL.createObjectURL(audioBlob);
              console.log('Created final audio URL from', audioChunks.length, 'chunks, total size:', combined.length, 'bytes');
            }
            
            // Store audio URL in the card for playback
            if (audioUrl) {
              setQACards(prev => {
                const updated = [...prev];
                const cardIndex = updated.findIndex(c => 
                  c.paragraphIndex === paragraphIndex && 
                  c.exchanges.length === 1 && 
                  c.exchanges[0].question === question
                );
                if (cardIndex >= 0) {
                  // Store audio URL in the exchange
                  updated[cardIndex] = {
                    ...updated[cardIndex],
                    exchanges: updated[cardIndex].exchanges.map((ex, idx) => 
                      idx === 0 ? { ...ex, audioUrl: audioUrl || undefined } : ex
                    )
                  };
                  // Also store in ref for quick access
                  if (audioUrl) {
                    qaAudioUrlsRef.current.set(cardId, audioUrl);
                  }
                }
                return updated;
              });
            }
            
            // Clear streaming state
            streamingAbortControllers.current.delete(cardId);
          },
          // onError
          (error: Error) => {
            // If 404, fallback to regular endpoint
            if (error.message.includes('404')) {
              console.log('Streaming endpoint not available, falling back to regular endpoint');
              // Fall through to regular endpoint below
              throw error;
            }
            console.error("Streaming error:", error);
            setIsLoadingAnswer(false);
            setError(error.message || "Failed to get answer. Please try again.");
            
            // Clear streaming state
            streamingAbortControllers.current.delete(cardId);
          },
          abortController.signal,
          // onAudioChunk - accumulate audio chunks (we'll create blob URL when stream completes)
          (audioBase64: string) => {
            try {
              console.log('Received audio chunk, length:', audioBase64.length);
              // Decode base64 audio and accumulate
              const audioBytes = Uint8Array.from(atob(audioBase64), c => c.charCodeAt(0));
              audioChunks.push(audioBytes);
              console.log('Accumulated audio chunks:', audioChunks.length);
              
              // Don't create blob URL yet - wait for stream to complete to avoid restart issues
              // We'll create it in onComplete
            } catch (e) {
              console.error('Failed to process audio chunk:', e);
            }
          }
        );
      } catch (streamError: any) {
        // If streaming fails (e.g., 404), fallback to regular endpoint
        if (streamError.message?.includes('404') || streamError.message?.includes('HTTP error')) {
          console.log('Streaming not available, using regular endpoint');
          streamingAbortControllers.current.delete(cardId);
          
          // Use regular chat endpoint
          const response = await sendChatMessage({
            message: question,
            context: lectureContext,
            ephemeral: true,
            sectionId: sectionId,
            chunkIndex: paragraphIndex,
          });
          
          console.log('✅ Received answer from chat API');
          
          // Extract answer and sources from chat response
          if (!response.messages || response.messages.length === 0) {
            throw new Error('Invalid response from chat API - no messages');
          }
          
          const lastMessage = response.messages[response.messages.length - 1];
          
          // Create card with answer (since we didn't create it during streaming)
          setIsLoadingAnswer(false);
          const newCard: QACard = {
            paragraphIndex,
            exchanges: [{
              question,
              answer: lastMessage.content,
              sources: lastMessage.sources || []
            }]
          };
          setQACards(prevCards => {
            const updated = [...prevCards, newCard];
            // Scroll to the new card after it's added
            setTimeout(() => {
              scrollToResumeButton(paragraphIndex, updated.length - 1);
            }, 100);
            return updated;
          });
        } else {
          // Re-throw if it's not a 404
          setIsLoadingAnswer(false);
          throw streamError;
        }
      }
      
      // Clear active input
      setActiveQuestionIndex(null);
      
      // PDF viewer will open only when user clicks a citation (same as chat)
      // No auto-open behavior
      
      // Note: Scrolling is now handled in the callbacks above after cards are created
      
    } catch (error) {
      console.error("Failed to get answer:", error);
      setError(error instanceof Error ? error.message : "Failed to get answer. Please try again.");
    } finally {
      setIsLoadingAnswer(false);
    }
  };

  const handleSubmitFollowUp = async (cardIndex: number, followUpQuestion: string) => {
    if (!followUpQuestion.trim()) return;
    
    const card = qaCards[cardIndex];
    const cardId = `${card.paragraphIndex}-${cardIndex}`;
    
    setIsLoadingFollowUp(cardId);
    setError(null);
    
    try {
      // Build previous Q&A context from all exchanges
      const previousContext = card.exchanges.map((ex, idx) => 
        `Question ${idx + 1}: ${ex.question}\nAnswer ${idx + 1}: ${ex.answer}`
      ).join('\n\n');
      
      // Get lecture context (same as before)
      const deliveredText = chunkMetadata
        ?.slice(0, card.paragraphIndex)
        .map(c => c.text)
        .join('\n\n') || '';
      
      const remainingText = chunkMetadata
        ?.slice(card.paragraphIndex)
        .map(c => c.text)
        .join('\n\n') || '';
      
      // Include figure information in context
      const figuresContext = lectureFigures && lectureFigures.length > 0
        ? `\n\n=== FIGURES SHOWN IN LECTURE ===
(Figures that have been displayed or will be displayed in this lecture)
${lectureFigures.map((fig, idx) => 
  `Figure ${idx + 1}: ${fig.caption || 'Untitled Figure'}
  - Description: ${fig.description || 'No description available'}
  - Page: ${fig.page}
  ${fig.explanation ? `- Explanation: ${fig.explanation}` : ''}`
).join('\n\n')}`
        : '';
      
      console.log('Submitting follow-up question to chat API:', { followUpQuestion });
      
      // Build lecture context for follow-up
      const lectureContext = `
You are continuing a lecture that was paused when a student raised their hand to ask a question.

IMPORTANT: Get straight to the answer. NO pleasantries like "Great question!" or "Good observation!" - just answer directly.

=== LECTURE DELIVERED SO FAR ===
(What the student has already heard)
${deliveredText || "(Nothing delivered yet - student paused at the very beginning)"}

=== LECTURE STILL TO COME ===
(What was about to be covered when student raised hand)
${remainingText || "(No remaining content - student is at the end of the lecture)"}
${figuresContext}

=== PREVIOUS QUESTION & ANSWER ===
${previousContext}

When answering, maintain the same conversational style as the lecture. If asked about future content, reference what's in "LECTURE STILL TO COME". If asked about figures, reference the figures shown in the lecture. Be concise and use numbered citations [1], [2] when referencing textbook material.
`.trim();
      
      // Add new exchange immediately with empty answer (will be filled via streaming)
      const exchangeId = `${cardId}-${card.exchanges.length}`;
      const updatedCards = [...qaCards];
      updatedCards[cardIndex] = {
        ...card,
        exchanges: [...card.exchanges, {
          question: followUpQuestion,
          answer: '', // Will be filled via streaming
          sources: []
        }]
      };
      setQACards(updatedCards);
      
      // Cancel any existing streaming for this exchange
      const existingController = streamingAbortControllers.current.get(exchangeId);
      if (existingController) {
        existingController.abort();
      }
      
      // Create abort controller for this stream
      const abortController = new AbortController();
      streamingAbortControllers.current.set(exchangeId, abortController);
      
      // Try streaming first, fallback to regular endpoint if not available
      try {
        await streamChatMessage(
          {
            message: followUpQuestion,
            context: lectureContext,
            ephemeral: true, // Don't create or persist session for lecture Q&A
            sectionId: sectionId, // Store Q&A tagged with section
            chunkIndex: card.paragraphIndex, // Store Q&A tagged with chunk/paragraph
          },
          // onChunk - update streaming answer as chunks arrive
          (chunk: string) => {
            setQACards(prevCards => {
              const updatedCards = [...prevCards];
              if (updatedCards[cardIndex] && updatedCards[cardIndex].exchanges.length > card.exchanges.length) {
                const exchangeIndex = updatedCards[cardIndex].exchanges.length - 1;
                const currentAnswer = updatedCards[cardIndex].exchanges[exchangeIndex]?.answer || '';
                updatedCards[cardIndex] = {
                  ...updatedCards[cardIndex],
                  exchanges: updatedCards[cardIndex].exchanges.map((ex, idx) => 
                    idx === exchangeIndex 
                      ? { ...ex, answer: currentAnswer + chunk }
                      : ex
                  )
                };
              }
              return updatedCards;
            });
          },
          // onComplete - finalize answer with sources
          (response: BackendChatResponse) => {
            console.log('✅ Follow-up stream complete, finalizing answer');
            
            // Extract answer and sources from response
            if (!response.messages || response.messages.length === 0) {
              throw new Error('Invalid response from chat API - no messages');
            }
            
            const lastMessage = response.messages[response.messages.length - 1];
            
            // Update card with final answer and sources
            setQACards(prevCards => {
              const updatedCards = [...prevCards];
              if (updatedCards[cardIndex]) {
                const exchangeIndex = updatedCards[cardIndex].exchanges.length - 1;
                updatedCards[cardIndex] = {
                  ...updatedCards[cardIndex],
                  exchanges: updatedCards[cardIndex].exchanges.map((ex, idx) => 
                    idx === exchangeIndex 
                      ? {
                          question: followUpQuestion,
                          answer: lastMessage.content,
                          sources: lastMessage.sources || []
                        }
                      : ex
                  )
                };
              }
              return updatedCards;
            });
            
            // Clear streaming state
            streamingAbortControllers.current.delete(exchangeId);
          },
          // onError
          (error: Error) => {
            // If 404, fallback to regular endpoint
            if (error.message.includes('404')) {
              console.log('Streaming endpoint not available, falling back to regular endpoint');
              throw error;
            }
            console.error("Follow-up streaming error:", error);
            setError(error.message || "Failed to get answer. Please try again.");
            streamingAbortControllers.current.delete(exchangeId);
          },
          abortController.signal
        );
      } catch (streamError: any) {
        // If streaming fails (e.g., 404), fallback to regular endpoint
        if (streamError.message?.includes('404') || streamError.message?.includes('HTTP error')) {
          console.log('Streaming not available, using regular endpoint for follow-up');
          streamingAbortControllers.current.delete(exchangeId);
          
          // Use regular chat endpoint
          const response = await sendChatMessage({
            message: followUpQuestion,
            context: lectureContext,
            ephemeral: true,
            sectionId: sectionId,
            chunkIndex: card.paragraphIndex,
          });
          
          console.log('✅ Received follow-up answer from chat API');
          
          // Extract answer and sources from chat response
          if (!response.messages || response.messages.length === 0) {
            throw new Error('Invalid response from chat API - no messages');
          }
          
          const lastMessage = response.messages[response.messages.length - 1];
          
          // Update card with final answer and sources
          setQACards(prevCards => {
            const updatedCards = [...prevCards];
            if (updatedCards[cardIndex]) {
              updatedCards[cardIndex] = {
                ...updatedCards[cardIndex],
                exchanges: [...updatedCards[cardIndex].exchanges, {
                  question: followUpQuestion,
                  answer: lastMessage.content,
                  sources: lastMessage.sources || []
                }]
              };
            }
            return updatedCards;
          });
        } else {
          // Re-throw if it's not a 404
          throw streamError;
        }
      }
      
      // PDF viewer will open only when user clicks a citation (same as chat)
      // No auto-open behavior
      
      // Scroll to position Resume Lecture button near bottom
      scrollToResumeButton(card.paragraphIndex, cardIndex);
      
    } catch (error) {
      console.error("Failed to get follow-up answer:", error);
      setError(error instanceof Error ? error.message : "Failed to get follow-up answer. Please try again.");
    } finally {
      setIsLoadingFollowUp(null);
    }
  };

  const handleResumeLecture = () => {
    // Clear any active question input
    setActiveQuestionIndex(null);
    
    // Close PDF reader when resuming lecture
    pdfViewer.closePdf();
    
    // Resume audio playback
    const audio = audioRef.current;
    if (audio && !isPlaying) {
      // isLoadingChunk is managed by the hook
      audio.play().then(() => {
        console.log("Resume promise resolved (waiting for actual playback)");
        // Don't set isPlaying here - wait for onPlay event
      }).catch(err => {
        console.error("Failed to resume playback:", err);
        // isLoadingChunk is managed by the hook
      });
    }
  };

  const handleGenerateAudio = async (cardIndex: number, exchangeIndex: number, answerText: string) => {
    try {
      console.log(`Generating audio for card ${cardIndex}, exchange ${exchangeIndex}`);
      const audioUrl = await generateAudioForText(answerText);
      
      // Update the exchange with the audio URL
      setQACards(prevCards => {
        const updatedCards = [...prevCards];
        if (updatedCards[cardIndex] && updatedCards[cardIndex].exchanges[exchangeIndex]) {
          updatedCards[cardIndex] = {
            ...updatedCards[cardIndex],
            exchanges: updatedCards[cardIndex].exchanges.map((ex, idx) => 
              idx === exchangeIndex ? { ...ex, audioUrl } : ex
            )
          };
        }
        return updatedCards;
      });
      
      console.log(`✅ Generated audio for card ${cardIndex}, exchange ${exchangeIndex}`);
    } catch (error) {
      console.error("Failed to generate audio:", error);
      throw error; // Re-throw so QACard can handle it
    }
  };

  const handleComplete = async () => {
    try {
      await completeSection(sectionId);
      if (onComplete) {
        onComplete();
      }
    } catch (err) {
      console.error("Failed to complete section:", err);
      setError(err instanceof Error ? err.message : "Failed to complete section");
    }
  };

  if (loading) {
    // Debug logging - only log every 5 seconds or on significant progress changes
    const now = Date.now();
    const timeSinceLastLog = now - lastLogTimeRef.current;
    const shouldLog = timeSinceLastLog > 5000 || progressPercent === 100 || currentStep.includes("Refining");
    if (shouldLog) {
      console.log("Rendering loading state:", {
        progressPercent,
        currentStep,
        elapsedSeconds,
      });
      lastLogTimeRef.current = now;
    }
    
    return (
      <GenerationProgress
        progressPercent={progressPercent}
        currentStep={currentStep}
        generationProgress={generationProgress}
        elapsedSeconds={elapsedSeconds}
        generationStartTime={generationStartTime}
      />
    );
  }

  if (error) {
    // Ensure error is always a string for rendering
    const errorMessage = typeof error === 'string' ? error : String(error);
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-4">
          <p className="text-red-700 font-medium mb-2">Error loading lecture</p>
          <p className="text-red-600 text-sm">{errorMessage}</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => {
              setError(null);
              setLoading(true);
              // Retry loading
              const loadLecture = async () => {
                try {
                  // Deduplicate: reuse existing promise if available
                  if (!getSectionLecturePromiseRef.current) {
                    getSectionLecturePromiseRef.current = getSectionLecture(sectionId);
                  }
                  const data = await getSectionLecturePromiseRef.current;
                  getSectionLecturePromiseRef.current = null; // Clear after use
                  setLectureScript(data.lectureScript);
                  setEstimatedMinutes(data.estimatedMinutes);
                  setLectureFigures(data.figures || []);
                  
                  // Load Q&A history if available
                  if (data.qaHistory) {
                    loadQAHistory(data.qaHistory);
                  }
                  
                  setError(null);
                } catch (err: any) {
                  console.error("Failed to load lecture:", err);
                  if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
                    setError("Lecture generation is taking longer than expected. Please try again - the lecture may have been generated.");
                  } else if (err.response?.status === 202 || err.isGenerationInProgress) {
                    // Generation in progress - this is fine, just wait
                    setError(null);
                    setLoading(true);
                  } else if (err.response?.data?.detail) {
                    // Ensure detail is a string, not an object
                    const detail = err.response.data.detail;
                    setError(typeof detail === 'string' ? detail : detail?.message || "Failed to load lecture");
                  } else if (err.message) {
                    setError(err.message);
                  } else {
                    setError("Failed to load lecture. Please check your connection and try again.");
                  }
                } finally {
                  setLoading(false);
                }
              };
              loadLecture();
            }}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Retry
          </button>
          <button
            onClick={handleBack}
            className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Back to Course
          </button>
        </div>
      </div>
    );
  }

  if (!lectureScript) {
    return (
      <div className="p-6 text-center text-gray-500">
        No lecture available for this section
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-2 border-b bg-white z-10">
        <div className="flex items-center gap-3">
          {/* Left side: Back arrow and Title */}
          <button
            onClick={handleBack}
            className="p-1 rounded-md hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            aria-label="Back to course"
          >
            <ArrowLeft className="w-5 h-5 text-gray-600" />
          </button>
          <div className="flex flex-col">
            <div className="flex items-baseline gap-3">
              <h2 className="text-xl font-bold">{sectionTitle || "Section Lecture"}</h2>
              <p className="text-sm text-gray-600">
                Estimated time: {estimatedMinutes} minutes
              </p>
            </div>
          </div>
          {/* Right side: Mark Complete */}
          <button
            onClick={handleComplete}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-green-600 text-white rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 ml-auto"
          >
            <CheckCircle className="w-4 h-4" />
            Mark Complete
          </button>
        </div>
      </div>
      
      {/* Audio player elements - hidden, custom controls in header */}
      {/* Main audio element for current chunk */}
      {lectureScript && (
        <audio
            ref={audioRef}
            preload="auto"
            style={{ display: 'none' }} // Hide completely - we use custom controls in header
            onLoadedMetadata={onLoadedMetadata}
            onPlay={onPlay}
            onPause={onPause}
            onTimeUpdate={onTimeUpdate}
            onEnded={onEnded}
            onError={onError}
          />
        )}
        {/* Preload audio element for next chunk (eliminates gaps between chunks) */}
        {lectureScript && (
          <audio
            ref={nextAudioRef}
            preload="auto"
            style={{ display: 'none' }} // Hide completely - used only for preloading
          />
        )}

      {/* Main Content Area - Split Screen Layout (matches chat structure) */}
      <div className="relative flex flex-1 overflow-hidden">
        {/* Lecture Content - uses chat's flex pattern */}
        <div className={`flex-1 flex flex-col border-r border-slate-300 transition-all duration-300 ${
          (pdfViewer.isOpen && lectureFigures && lectureFigures.length > 0) ? 'w-1/3' : 
          ((pdfViewer.isOpen || (lectureFigures && lectureFigures.length > 0)) ? 'w-1/2' : 'w-full')
        }`}>
          <main className="flex-1 overflow-y-auto bg-slate-50 px-4 py-6">
            {/* Add left padding (pl-28 = 112px) to make room for absolutely positioned buttons at -left-24 (96px) */}
            <div className="max-w-3xl mx-auto pl-28">
          <div className="prose prose-slate max-w-none">
            {/* Figures are now displayed in the right sidebar, not here */}
            {chunkMetadata && chunkMetadata.length > 0 ? (
              // Render with chunk highlighting by paragraph
              <div className="text-gray-800 leading-relaxed space-y-4">
                {chunkMetadata.map((chunk, index) => {
                  // Check if this chunk contains figure links
                  const hasFigureLinks = chunk.text && chunk.text.includes('figure-link');
                  if (hasFigureLinks) {
                    console.log(`Chunk ${index} contains figure links:`, chunk.text.substring(0, 200));
                  }
                  return (
                    <div key={index}>
                    {/* Paragraph text */}
                    <div
                      ref={(el) => {
                        if (el) {
                          chunkRefs.current.set(index, el);
                        } else {
                          chunkRefs.current.delete(index);
                        }
                      }}
                      onClick={() => handleChunkClick(index)}
                      className={`transition-colors duration-300 rounded px-2 py-1 cursor-pointer hover:bg-gray-100 relative ${
                        currentChunkIndex === index
                          ? "bg-yellow-50/50" // Subtle 5% yellow highlighting, no border
                          : ""
                      }`}
                    >
                      <div dangerouslySetInnerHTML={{ __html: chunk.text }} />
                      {/* Play and Raised Hand buttons next to current chunk */}
                      {currentChunkIndex === index && (
                        <div className="absolute -left-28 top-3 flex flex-col items-center gap-2">
                          {/* Play button */}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handlePlayPause();
                            }}
                            disabled={isLoadingChunk}
                            className="p-2 rounded-full bg-blue-600 text-white hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed shadow-lg"
                            title={isPlaying ? "Pause" : "Play"}
                          >
                            {isLoadingChunk ? (
                              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                            ) : isPlaying ? (
                              <Pause className="w-5 h-5" />
                            ) : (
                              <Play className="w-5 h-5 ml-0.5" />
                            )}
                          </button>
                          {/* Playback speed control - below play button */}
                          {!isLoadingChunk && audioAvailable !== false && (
                            <select
                              id="playback-speed-inline"
                              value={playbackSpeed}
                              onChange={async (e) => {
                                const speed = parseFloat(e.target.value);
                                setPlaybackSpeed(speed);
                                try {
                                  await updatePlaybackSpeed(speed);
                                  console.log("Playback speed preference updated:", speed);
                                } catch (error) {
                                  console.error("Failed to update playback speed preference:", error);
                                }
                                if (audioRef.current) {
                                  audioRef.current.playbackRate = speed;
                                }
                              }}
                              className="text-[10px] border border-gray-300 rounded-full px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 shadow"
                            >
                              <option value="0.5">0.5x</option>
                              <option value="0.75">0.75x</option>
                              <option value="1">1x</option>
                              <option value="1.25">1.25x</option>
                              <option value="1.5">1.5x</option>
                              <option value="1.75">1.75x</option>
                              <option value="2">2x</option>
                            </select>
                          )}
                          {/* Raised Hand button */}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleRaiseHand(index);
                            }}
                            disabled={activeQuestionIndex === index}
                            className="p-2 rounded-full bg-yellow-500 text-white hover:bg-yellow-600 disabled:bg-gray-400 disabled:cursor-not-allowed shadow-lg"
                            title="Ask a question"
                          >
                            <Hand className="w-5 h-5" />
                          </button>
                        </div>
                      )}
                    </div>
                    
                    {/* Question input if active at this paragraph */}
                    {activeQuestionIndex === index && (
                      <div className="my-4 p-4 bg-blue-50 border-2 border-blue-200 rounded-lg">
                        <h4 className="font-semibold text-blue-900 mb-2">Ask a Question</h4>
                        <textarea
                          autoFocus
                          rows={3}
                          className="w-full p-2 border border-blue-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                          placeholder="Type your question here..."
                          id={`question-input-${index}`}
                        />
                        <div className="mt-2 flex gap-2">
                          <button
                            onClick={() => {
                              const textarea = document.getElementById(`question-input-${index}`) as HTMLTextAreaElement;
                              if (textarea) {
                                handleSubmitQuestion(index, textarea.value);
                              }
                            }}
                            disabled={isLoadingAnswer}
                            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400"
                          >
                            {isLoadingAnswer ? 'Getting answer...' : 'Submit Question'}
                          </button>
                          <button
                            onClick={() => setActiveQuestionIndex(null)}
                            className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    )}
                    
                    {/* Q&A cards for this paragraph */}
                    {qaCards
                      .filter(card => card.paragraphIndex === index)
                      .map((card, cardIdx) => {
                        const cardId = `${card.paragraphIndex}-${cardIdx}`;
                        const isThisCardLoading = isLoadingFollowUp === cardId;
                        const cardIndex = qaCards.findIndex(c => 
                          c.paragraphIndex === card.paragraphIndex
                        );
                        
                        return (
                          <QACard
                            key={cardIdx}
                            card={card}
                            cardIndex={cardIndex}
                            cardId={cardId}
                            paragraphIndex={index}
                            isThisCardLoading={isThisCardLoading}
                            playbackSpeed={playbackSpeed}
                            onFollowUp={handleSubmitFollowUp}
                            onResumeLecture={handleResumeLecture}
                            onCitationClick={(citationId, sources) => {
                              pdfViewer.openPdfFromCitation(citationId, sources);
                            }}
                            onGenerateAudio={handleGenerateAudio}
                          />
                        );
                      })}
                    </div>
                  );
                })}
                
                {/* Q&A card for end-of-lecture questions */}
                {activeQuestionIndex === chunkMetadata.length && (
                  <div className="my-4 p-4 bg-blue-50 border-2 border-blue-200 rounded-lg">
                    <h4 className="font-semibold text-blue-900 mb-2">Ask a Question</h4>
                    <textarea
                      autoFocus
                      rows={3}
                      className="w-full p-2 border border-blue-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="Type your question about the lecture..."
                      id={`question-input-end`}
                    />
                    <div className="mt-2 flex gap-2">
                      <button
                        onClick={() => {
                          const textarea = document.getElementById(`question-input-end`) as HTMLTextAreaElement;
                          if (textarea) {
                            handleSubmitQuestion(chunkMetadata.length, textarea.value);
                          }
                        }}
                        disabled={isLoadingAnswer}
                        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400"
                      >
                        {isLoadingAnswer ? 'Getting answer...' : 'Submit Question'}
                      </button>
                      <button
                        onClick={() => setActiveQuestionIndex(null)}
                        className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
                
                {qaCards
                  .filter(card => card.paragraphIndex === chunkMetadata.length)
                  .map((card, cardIdx) => {
                    const cardId = `end-${cardIdx}`;
                    const isThisCardLoading = isLoadingFollowUp === cardId;
                    const cardIndex = qaCards.findIndex(c => 
                      c.paragraphIndex === card.paragraphIndex
                    );
                    
                    return (
                      <QACard
                        key={cardIdx}
                        card={card}
                        cardIndex={cardIndex}
                        cardId={cardId}
                        paragraphIndex={-1} // Use -1 to indicate "end" for ID generation
                        isThisCardLoading={isThisCardLoading}
                        playbackSpeed={playbackSpeed}
                        onFollowUp={handleSubmitFollowUp}
                        onResumeLecture={handleResumeLecture}
                        onCitationClick={(citationId, sources) => {
                          pdfViewer.openPdfFromCitation(citationId, sources);
                        }}
                        onGenerateAudio={handleGenerateAudio}
                      />
                    );
                  })}
              </div>
            ) : (
              // Fallback: render without chunking if metadata not available
              <div className="whitespace-pre-wrap text-gray-800 leading-relaxed">
                {lectureScript}
              </div>
            )}
          </div>
            </div>
          </main>
        </div>
        
        {/* PDF Reader Panel - slides in from right when opened */}
        {pdfViewer.isOpen && (
          <div className={`flex-1 ${lectureFigures && lectureFigures.length > 0 ? 'w-1/3' : 'w-1/2'} bg-white transition-all duration-300 flex flex-col overflow-hidden`}>
            {(() => {
              console.log('[SectionPlayer] Rendering PDFViewer, isOpen:', pdfViewer.isOpen, 'bookId:', pdfViewer.bookId, 'page:', pdfViewer.page);
              return pdfViewer.bookId ? (
                <PDFViewer
                  bookId={pdfViewer.bookId}
                  initialPage={pdfViewer.page}
                  bookTitle={pdfViewer.bookTitle}
                  onClose={pdfViewer.closePdf}
                />
              ) : (
                <PDFViewerEmpty />
              );
            })()}
          </div>
        )}
        
        {/* Figure Viewer Panel - shows figures on the right when available (or when PDF is open if user wants to see both) */}
        {lectureFigures && lectureFigures.length > 0 && (
          <div className={`flex-1 ${pdfViewer.isOpen ? 'w-1/3' : 'w-1/2'} bg-white border-l border-slate-300 transition-all duration-300 overflow-y-auto`}>
            <div className="p-4">
              <h3 className="text-lg font-semibold mb-4 text-slate-800">Figures ({lectureFigures.length})</h3>
              <div className="space-y-6">
                {lectureFigures.map((figure) => {
                  // Use the API client's base URL to ensure correct backend connection
                  // API_URL automatically detects tunnel URLs (from client.ts)
                  // API_URL already includes /api, so we just need to add the path
                  const imageUrl = `${API_URL}/mna-expert/figures/${figure.figure_id}/image`;
                  return (
                    <FigureViewerItem key={figure.figure_id} figure={figure} imageUrl={imageUrl} />
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

