/**
 * Pure functions for audio and chunk calculations.
 * 
 * These functions contain no side effects and can be easily tested.
 * They follow the functional programming principles: same inputs always produce same outputs.
 */

export interface ChunkMetadata {
  text: string;
  start_proportion: number;  // 0.0 to 1.0 - proportion of total audio duration
  end_proportion: number;    // 0.0 to 1.0 - proportion of total audio duration
}

/**
 * Calculate which chunk should be highlighted based on current playback time.
 * 
 * This is a pure function: same inputs always produce same outputs, no side effects.
 * Uses proportional positions (0.0 to 1.0) multiplied by actual audio duration.
 * No time estimates - only uses actual audio duration when available.
 * 
 * @param currentTime - Current playback time in seconds
 * @param playbackSpeed - Playback speed multiplier (1.0 = normal, 1.5 = 1.5x, etc.)
 * @param chunkMetadata - Array of chunk metadata with start/end proportions (0.0 to 1.0)
 * @param actualAudioDuration - Actual duration of audio in seconds (if available, otherwise null)
 * @returns Index of chunk to highlight, or null if no chunk should be highlighted
 */
export function calculateCurrentChunk(
  currentTime: number,
  playbackSpeed: number,
  chunkMetadata: ChunkMetadata[],
  actualAudioDuration: number | null
): number | null {
  // Validate inputs
  if (isNaN(currentTime) || currentTime < 0) {
    return null;
  }
  
  if (!chunkMetadata || chunkMetadata.length === 0) {
    return null;
  }
  
  // We need actual audio duration to calculate which chunk is playing
  // Without it, we can't accurately map proportions to time
  const hasValidDuration = actualAudioDuration && 
                           actualAudioDuration > 0 && 
                           isFinite(actualAudioDuration);
  
  if (!hasValidDuration) {
    // Can't highlight without actual duration - return null
    // This prevents drift from estimates
    return null;
  }
  
  // Account for playback speed - proportions are based on 1x speed
  // At 1.5x playback speed, 10 seconds of playback = 15 seconds of 1x content
  const adjustedTime = currentTime * playbackSpeed;
  
  // Calculate current position as proportion of total duration (0.0 to 1.0)
  const currentProportion = adjustedTime / actualAudioDuration;
  
  // Find chunk that contains this proportion
  for (let i = 0; i < chunkMetadata.length; i++) {
    const chunk = chunkMetadata[i];
    if (currentProportion >= chunk.start_proportion && currentProportion < chunk.end_proportion) {
      return i;
    }
  }
  
  // Past the end - return last chunk
  if (currentProportion >= chunkMetadata[chunkMetadata.length - 1].end_proportion) {
    return chunkMetadata.length - 1;
  }
  
  // Before start
  if (currentProportion < chunkMetadata[0].start_proportion) {
    return null;
  }
  
  return null;
}

/**
 * Calculate the target playback time for a chunk index.
 * 
 * Uses proportional positions (0.0 to 1.0) multiplied by actual audio duration.
 * 
 * @param chunkIndex - Index of the chunk to skip to
 * @param chunkMetadata - Array of chunk metadata with start/end proportions (0.0 to 1.0)
 * @param playbackSpeed - Current playback speed multiplier
 * @param actualAudioDuration - Actual duration of audio in seconds (required for mapping proportions to time)
 * @returns Target playback time in seconds, or 0 if chunk not found or duration not available
 */
export function calculateChunkPlaybackTime(
  chunkIndex: number,
  chunkMetadata: ChunkMetadata[],
  playbackSpeed: number,
  actualAudioDuration: number | null
): number {
  if (chunkIndex < 0 || chunkIndex >= chunkMetadata.length) {
    return 0;
  }
  
  // If totalAudioDuration is not available or invalid, we cannot map proportions to time
  if (!actualAudioDuration || !isFinite(actualAudioDuration) || actualAudioDuration <= 0) {
    return 0;
  }
  
  const chunk = chunkMetadata[chunkIndex];
  const targetProportion = chunk.start_proportion;
  
  // Convert from proportional position to actual playback time
  // targetTime = (targetProportion * totalAudioDuration) / playbackSpeed
  return (targetProportion * actualAudioDuration) / playbackSpeed;
}

