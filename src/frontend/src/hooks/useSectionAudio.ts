import { useState, useEffect, useRef, useCallback } from "react";
import { getSectionAudioChunkUrl } from "../api/courses";
import type { ChunkMetadata } from "../api/courses";

interface UseSectionAudioProps {
  sectionId: string;
  chunkMetadata: ChunkMetadata[] | null;
  playbackSpeed: number;
  setCurrentChunkIndex: (index: number | null) => void;
  setError: (error: string | null) => void;
}

interface UseSectionAudioReturn {
  // State
  isPlaying: boolean;
  isLoadingChunk: boolean;
  audioAvailable: boolean | null;
  generatingAudio: boolean;
  audioBlobUrl: string | null;
  currentChunkIndex: number | null;
  
  // Refs
  audioRef: React.RefObject<HTMLAudioElement>;
  nextAudioRef: React.RefObject<HTMLAudioElement>;
  
  // Handlers
  handlePlayPause: () => Promise<void>;
  handleChunkClick: (chunkIndex: number) => void;
  
  // Audio event handlers
  onPlay: () => void;
  onPause: () => void;
  onTimeUpdate: () => void;
  onEnded: () => void;
  onError: (e: React.SyntheticEvent<HTMLAudioElement, Event>) => void;
  onLoadedMetadata: () => void;
}

/**
 * Custom hook for managing section audio playback.
 * Handles chunk-by-chunk playback, preloading, and audio state management.
 */
export const useSectionAudio = ({
  sectionId,
  chunkMetadata,
  playbackSpeed,
  setCurrentChunkIndex,
  setError,
}: UseSectionAudioProps): UseSectionAudioReturn => {
  // Audio state
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoadingChunk, setIsLoadingChunk] = useState(false);
  const [audioAvailable, setAudioAvailable] = useState<boolean | null>(null);
  const [generatingAudio, setGeneratingAudio] = useState(false);
  const [audioBlobUrl, setAudioBlobUrl] = useState<string | null>(null);
  const [currentChunkIndex, setCurrentChunkIndexInternal] = useState<number | null>(null);
  
  // Audio refs
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const nextAudioRef = useRef<HTMLAudioElement | null>(null);
  
  // Preloading state
  const preloadedChunkBlobs = useRef<Map<number, string>>(new Map());
  const preloadingChunks = useRef<Set<number>>(new Set());
  const pausedPositionRef = useRef<number>(0);
  const timeupdateListenerRef = useRef<(() => void) | null>(null);
  
  // Update currentChunkIndex in parent component when it changes
  useEffect(() => {
    setCurrentChunkIndex(currentChunkIndex);
  }, [currentChunkIndex, setCurrentChunkIndex]);
  
  // Preload chunk 0 immediately when sectionId is available
  useEffect(() => {
    if (!sectionId) return;
    
    if (!preloadedChunkBlobs.current.has(0) && !preloadingChunks.current.has(0)) {
      preloadingChunks.current.add(0);
      const chunk0Url = getSectionAudioChunkUrl(sectionId, 0);
      console.log("🚀 Preloading chunk 1 immediately (before metadata)...");
      fetch(chunk0Url)
        .then(response => {
          if (!response.ok) throw new Error("Failed to fetch chunk 0");
          return response.blob();
        })
        .then(blob => {
          const blobUrl = URL.createObjectURL(blob);
          preloadedChunkBlobs.current.set(0, blobUrl);
          preloadingChunks.current.delete(0);
          console.log(`✅ Preloaded chunk 1 as blob (ready for instant playback)`);
        })
        .catch(err => {
          preloadingChunks.current.delete(0);
          console.log("Chunk 1 preload failed (will retry when metadata loads):", err.message);
        });
    }
  }, [sectionId]);
  
  // Retry preloading chunk 0 when metadata loads
  useEffect(() => {
    if (!chunkMetadata || chunkMetadata.length === 0) return;
    
    if (!preloadedChunkBlobs.current.has(0) && !preloadingChunks.current.has(0)) {
      preloadingChunks.current.add(0);
      const chunk0Url = getSectionAudioChunkUrl(sectionId, 0);
      console.log("Preloading chunk 1 as blob (retry after metadata load)...");
      fetch(chunk0Url)
        .then(response => {
          if (!response.ok) throw new Error("Failed to fetch chunk 0");
          return response.blob();
        })
        .then(blob => {
          const blobUrl = URL.createObjectURL(blob);
          preloadedChunkBlobs.current.set(0, blobUrl);
          preloadingChunks.current.delete(0);
          console.log(`✅ Preloaded chunk 1 as blob (ready for instant playback)`);
        })
        .catch(err => {
          preloadingChunks.current.delete(0);
          console.log("Failed to preload chunk 0 (will use streaming):", err.message);
        });
    }
  }, [sectionId, chunkMetadata]);
  
  // Helper function to preload chunks ahead
  const preloadAhead = useCallback((fromIndex: number) => {
    if (!chunkMetadata) return;
    
    // Preload chunk N+1
    if (fromIndex + 1 < chunkMetadata.length) {
      const chunkIndex = fromIndex + 1;
      if (!preloadedChunkBlobs.current.has(chunkIndex) && !preloadingChunks.current.has(chunkIndex)) {
        preloadingChunks.current.add(chunkIndex);
        const url = getSectionAudioChunkUrl(sectionId, chunkIndex);
        fetch(url)
          .then(response => {
            if (!response.ok) throw new Error(`Failed to fetch chunk ${chunkIndex + 1}`);
            return response.blob();
          })
          .then(blob => {
            const blobUrl = URL.createObjectURL(blob);
            preloadedChunkBlobs.current.set(chunkIndex, blobUrl);
            preloadingChunks.current.delete(chunkIndex);
            console.log(`✅ Preloaded chunk ${chunkIndex + 1} as blob`);
          })
          .catch(err => {
            preloadingChunks.current.delete(chunkIndex);
            console.error(`Failed to preload chunk ${chunkIndex + 1}:`, err);
          });
      }
    }
    
    // Preload chunk N+2
    if (fromIndex + 2 < chunkMetadata.length) {
      const chunkIndex = fromIndex + 2;
      if (!preloadedChunkBlobs.current.has(chunkIndex) && !preloadingChunks.current.has(chunkIndex)) {
        preloadingChunks.current.add(chunkIndex);
        const url = getSectionAudioChunkUrl(sectionId, chunkIndex);
        fetch(url)
          .then(response => {
            if (!response.ok) throw new Error(`Failed to fetch chunk ${chunkIndex + 1}`);
            return response.blob();
          })
          .then(blob => {
            const blobUrl = URL.createObjectURL(blob);
            preloadedChunkBlobs.current.set(chunkIndex, blobUrl);
            preloadingChunks.current.delete(chunkIndex);
            console.log(`✅ Preloaded chunk ${chunkIndex + 1} as blob (2 ahead)`);
          })
          .catch(err => {
            preloadingChunks.current.delete(chunkIndex);
            console.error(`Failed to preload chunk ${chunkIndex + 1}:`, err);
          });
      }
    }
  }, [sectionId, chunkMetadata]);
  
  // Handle chunk click - jump to specific chunk
  const handleChunkClick = useCallback((chunkIndex: number) => {
    console.log(`Clicked chunk ${chunkIndex + 1}, jumping to it...`);
    
    setCurrentChunkIndexInternal(chunkIndex);
    
    // Preload this chunk if not already preloaded
    if (!preloadedChunkBlobs.current.has(chunkIndex) && !preloadingChunks.current.has(chunkIndex)) {
      preloadingChunks.current.add(chunkIndex);
      const chunkUrl = getSectionAudioChunkUrl(sectionId, chunkIndex);
      console.log(`Preloading clicked chunk ${chunkIndex + 1}...`);
      fetch(chunkUrl)
        .then(response => {
          if (!response.ok) throw new Error(`Failed to fetch chunk ${chunkIndex}`);
          return response.blob();
        })
        .then(blob => {
          const blobUrl = URL.createObjectURL(blob);
          preloadedChunkBlobs.current.set(chunkIndex, blobUrl);
          preloadingChunks.current.delete(chunkIndex);
          console.log(`✅ Preloaded clicked chunk ${chunkIndex + 1}`);
        })
        .catch(err => {
          preloadingChunks.current.delete(chunkIndex);
          console.error(`Failed to preload chunk ${chunkIndex}:`, err);
        });
    }
    
    // Preload chunks ahead when jumping to a chunk
    preloadAhead(chunkIndex);
    
    // If audio is playing, load and play the clicked chunk
    if (isPlaying) {
      const audio = audioRef.current;
      if (audio && chunkMetadata) {
        audio.pause();
        setIsPlaying(false);
        
        const blobUrl = preloadedChunkBlobs.current.get(chunkIndex);
        const chunkUrl = getSectionAudioChunkUrl(sectionId, chunkIndex);
        
        if (blobUrl) {
          audio.src = blobUrl;
        } else {
          audio.src = chunkUrl;
        }
        
        audio.playbackRate = playbackSpeed;
        setIsLoadingChunk(true);
        audio.play().then(() => {
          console.log(`Play promise resolved for clicked chunk ${chunkIndex + 1} (waiting for actual playback)`);
        }).catch(err => {
          console.error("Failed to play clicked chunk:", err);
          setIsLoadingChunk(false);
        });
      }
    }
  }, [sectionId, chunkMetadata, isPlaying, playbackSpeed, preloadAhead]);
  
  // Handle play/pause
  const handlePlayPause = useCallback(async () => {
    if (!chunkMetadata || chunkMetadata.length === 0) {
      console.error("Cannot play: chunk metadata not loaded");
      return;
    }
    
    let audio = audioRef.current;
    if (!audio) {
      await new Promise(resolve => setTimeout(resolve, 50));
      audio = audioRef.current;
    }
    
    if (!audio) {
      console.error("Audio element not found after waiting");
      return;
    }
    
    if (isPlaying) {
      // Pause
      const currentTime = audio.currentTime;
      const currentIndex = currentChunkIndex;
      console.log(`Pausing at chunk ${currentIndex !== null ? currentIndex + 1 : '?'}, time ${currentTime.toFixed(2)}s`);
      pausedPositionRef.current = currentTime;
      audio.pause();
      setIsPlaying(false);
    } else {
      // Start/resume playing
      const startChunkIndex = currentChunkIndex !== null ? currentChunkIndex : 0;
      const chunkUrl = getSectionAudioChunkUrl(sectionId, startChunkIndex);
      const blobUrl = preloadedChunkBlobs.current.get(startChunkIndex);
      
      const isResuming = (audio.src === chunkUrl || audio.src === blobUrl) && pausedPositionRef.current > 0;
      
      console.log(`Starting/resuming playback from chunk ${startChunkIndex + 1}/${chunkMetadata.length}... (resuming: ${isResuming}, pausedPosition: ${pausedPositionRef.current.toFixed(2)}s)`);
      
      if (isResuming) {
        // Resuming in the middle of a chunk
        if (audio.currentTime !== pausedPositionRef.current) {
          audio.currentTime = pausedPositionRef.current;
        }
        setIsLoadingChunk(true);
        audio.play().then(() => {
          console.log(`Resume promise resolved for chunk ${startChunkIndex + 1} (waiting for actual playback)`);
        }).catch(err => {
          console.error("Failed to resume:", err);
          setIsLoadingChunk(false);
        });
      } else {
        // Starting new chunk
        pausedPositionRef.current = 0;
        setIsLoadingChunk(true);
        setCurrentChunkIndexInternal(startChunkIndex);
        setAudioAvailable(true);
        
        if (startChunkIndex === 0) {
          // First chunk: use blob if preloaded
          const blobUrl0 = preloadedChunkBlobs.current.get(0);
          if (blobUrl0) {
            console.log("Using preloaded blob for chunk 1 (instant playback)");
            audio.src = blobUrl0;
            audio.playbackRate = playbackSpeed;
          } else {
            console.log("Streaming chunk 1 directly (not preloaded yet)");
            audio.src = chunkUrl;
            audio.playbackRate = playbackSpeed;
          }
          preloadAhead(0);
        } else {
          // Subsequent chunks
          if (blobUrl) {
            audio.src = blobUrl;
            audio.playbackRate = playbackSpeed;
          } else {
            audio.src = chunkUrl;
            audio.playbackRate = playbackSpeed;
          }
          preloadAhead(startChunkIndex);
        }
        
        const playPromise = audio.play();
        if (playPromise !== undefined) {
          playPromise
            .then(() => {
              console.log(`Play promise resolved for chunk ${startChunkIndex + 1} (waiting for actual playback to start)`);
            })
            .catch(err => {
              console.log(`Immediate play failed (will retry when data arrives): ${err.message}`);
              const handleLoadedData = () => {
                if (audio && audio.readyState >= 2 && !isPlaying) {
                  audio.play()
                    .then(() => {
                      console.log(`Play promise resolved on loadeddata for chunk ${startChunkIndex + 1}`);
                    })
                    .catch(playErr => {
                      console.log("Play on loadeddata failed:", playErr);
                      setIsLoadingChunk(false);
                    });
                }
                audio?.removeEventListener('loadeddata', handleLoadedData);
              };
              audio.addEventListener('loadeddata', handleLoadedData, { once: true });
            });
        }
      }
    }
  }, [chunkMetadata, isPlaying, currentChunkIndex, sectionId, playbackSpeed, preloadAhead]);
  
  // Audio event handlers
  const onPlay = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    
    console.log("Audio play event fired - waiting for timeupdate to confirm actual playback...");
    audio.playbackRate = playbackSpeed;
    
    if (timeupdateListenerRef.current) {
      audio.removeEventListener('timeupdate', timeupdateListenerRef.current);
      timeupdateListenerRef.current = null;
    }
    
    let fallbackTimeout: ReturnType<typeof setTimeout> | null = null;
    
    const handleTimeUpdate = () => {
      const currentAudio = audioRef.current;
      if (currentAudio && !currentAudio.paused && currentAudio.currentTime > 0) {
        console.log("Audio confirmed playing via timeupdate (currentTime:", currentAudio.currentTime.toFixed(2), "s)");
        setIsPlaying(true);
        setIsLoadingChunk(false);
        setGeneratingAudio(false);
        
        if (timeupdateListenerRef.current && currentAudio) {
          currentAudio.removeEventListener('timeupdate', timeupdateListenerRef.current);
          timeupdateListenerRef.current = null;
        }
        if (fallbackTimeout !== null) {
          clearTimeout(fallbackTimeout);
          fallbackTimeout = null;
        }
      }
    };
    
    audio.addEventListener('timeupdate', handleTimeUpdate, { once: false });
    timeupdateListenerRef.current = handleTimeUpdate;
    
    fallbackTimeout = setTimeout(() => {
      const currentAudio = audioRef.current;
      if (currentAudio && !currentAudio.paused && currentAudio.currentTime > 0) {
        console.log("Fallback: Audio appears to be playing after 2s timeout");
        setIsPlaying(true);
        setIsLoadingChunk(false);
        setGeneratingAudio(false);
        if (timeupdateListenerRef.current && currentAudio) {
          currentAudio.removeEventListener('timeupdate', timeupdateListenerRef.current);
          timeupdateListenerRef.current = null;
        }
      }
      fallbackTimeout = null;
    }, 2000);
  }, [playbackSpeed]);
  
  const onPause = useCallback(() => {
    console.log("Audio paused");
    setIsPlaying(false);
  }, []);
  
  const onTimeUpdate = useCallback(() => {
    // Time update logic can be added here if needed
  }, []);
  
  const onEnded = useCallback(() => {
    // Handle chunk ended - switch to next chunk
    const currentIndex = currentChunkIndex !== null ? currentChunkIndex : -1;
    const nextIndex = currentIndex + 1;
    
    if (!chunkMetadata || nextIndex >= chunkMetadata.length) {
      // Reached end
      setIsPlaying(false);
      setIsLoadingChunk(false);
      setCurrentChunkIndexInternal(null);
      return;
    }
    
    const audio = audioRef.current;
    if (!audio) return;
    
    const preloadedBlobUrl = preloadedChunkBlobs.current.get(nextIndex);
    
    if (preloadedBlobUrl) {
      // Next chunk is preloaded
      console.log(`Chunk ${currentIndex + 1} finished, switching to preloaded blob chunk ${nextIndex + 1} instantly...`);
      setCurrentChunkIndexInternal(nextIndex);
      setIsLoadingChunk(false);
      
      audio.src = preloadedBlobUrl;
      audio.playbackRate = playbackSpeed;
      audio.load();
      
      audio.play().then(() => {
        console.log(`Play promise resolved for preloaded chunk ${nextIndex + 1} (waiting for actual playback)`);
      }).catch(err => {
        console.error("Failed to play preloaded blob:", err);
        setIsPlaying(false);
      });
      
      preloadAhead(nextIndex);
    } else {
      // Next chunk not preloaded - stream it
      console.log(`Chunk ${currentIndex + 1} finished, streaming chunk ${nextIndex + 1} (not preloaded yet)...`);
      setIsLoadingChunk(true);
      setCurrentChunkIndexInternal(nextIndex);
      
      const nextChunkUrl = getSectionAudioChunkUrl(sectionId, nextIndex);
      audio.src = nextChunkUrl;
      audio.playbackRate = playbackSpeed;
      
      setIsLoadingChunk(true);
      audio.play().then(() => {
        console.log(`Play promise resolved for chunk ${nextIndex + 1} (waiting for actual playback)`);
      }).catch(err => {
        console.log(`Immediate play failed (will auto-play when data arrives): ${err}`);
        setIsLoadingChunk(false);
      });
      
      // Listen for loadeddata
      const handleLoadedData = () => {
        if (audio && audio.readyState >= 2 && !isPlaying) {
          audio.play()
            .then(() => {
              console.log(`Play promise resolved on loadeddata for chunk ${nextIndex + 1}`);
            })
            .catch(() => {
              setIsLoadingChunk(false);
            });
        }
        audio.removeEventListener('loadeddata', handleLoadedData);
      };
      audio.addEventListener('loadeddata', handleLoadedData);
      
      // Fallback: also listen for canplay
      audio.addEventListener('canplay', () => {
        if (audio && !isPlaying) {
          audio.play()
            .then(() => {
              console.log(`Play promise resolved on canplay for chunk ${nextIndex + 1}`);
            })
            .catch(err => {
              console.error("Failed to play next chunk:", err);
              setIsLoadingChunk(false);
            });
        }
      }, { once: true });
      
      preloadAhead(nextIndex);
    }
  }, [currentChunkIndex, chunkMetadata, sectionId, playbackSpeed, isPlaying, preloadAhead]);
  
  const onError = useCallback((e: React.SyntheticEvent<HTMLAudioElement, Event>) => {
    const audio = audioRef.current;
    const errorDetails = {
      error: audio?.error,
      errorCode: audio?.error?.code,
      errorMessage: audio?.error?.message,
      networkState: audio?.networkState,
      readyState: audio?.readyState,
      src: audio?.src,
      currentSrc: audio?.currentSrc,
      blobUrl: audioBlobUrl,
    };
    console.error("Audio load error:", e);
    console.error("Audio error details:", errorDetails);
    
    if (audio?.error?.code === 4) {
      if (generatingAudio) {
        console.log("Stream not ready yet (error 4) - will retry in 2 seconds...");
        setTimeout(() => {
          if (audioRef.current && audioBlobUrl && generatingAudio) {
            console.log("Retrying audio load after delay...");
            audioRef.current.src = audioBlobUrl;
            audioRef.current.load();
          }
        }, 2000);
      } else {
        console.log("Stream error after generation (error 4) - retrying...");
        setTimeout(() => {
          if (audioRef.current && audioBlobUrl) {
            console.log("Retrying audio load...");
            audioRef.current.src = audioBlobUrl;
            audioRef.current.load();
          }
        }, 1000);
      }
      return;
    }
    
    console.warn("Audio error (non-fatal):", errorDetails);
  }, [audioBlobUrl, generatingAudio]);
  
  const onLoadedMetadata = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = playbackSpeed;
    }
  }, [playbackSpeed]);
  
  return {
    // State
    isPlaying,
    isLoadingChunk,
    audioAvailable,
    generatingAudio,
    audioBlobUrl,
    currentChunkIndex,
    
    // Refs
    audioRef,
    nextAudioRef,
    
    // Handlers
    handlePlayPause,
    handleChunkClick,
    
    // Audio event handlers
    onPlay,
    onPause,
    onTimeUpdate,
    onEnded,
    onError,
    onLoadedMetadata,
  };
};

