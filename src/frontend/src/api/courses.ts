import { apiClient } from "./client";
import type {
  Course,
  CourseOutline,
  CoursePart,
  CourseSection,
  SectionDelivery,
  CreateCourseRequest,
  CreateCourseResponse,
  StandaloneSectionRequest,
  CoursePreferences,
  SectionStatus,
} from "../types/course";

// Raw API response types (snake_case)
interface RawCourse {
  course_id: string;
  user_id: string;
  title: string;
  original_query: string;
  estimated_hours: number;
  created_at: string;
  last_modified: string;
  preferences: {
    depth: string;
    presentation_style: string;
    pace: string;
    additional_notes?: string;
  };
  status: string;
}

interface RawCourseSection {
  section_id: string;
  course_id: string;
  parent_section_id?: string;
  order_index: number;
  title: string;
  learning_objectives: string[];
  content_summary?: string;
  estimated_minutes: number;
  chunk_ids: string[];
  status: string;
  completed_at?: string;
  can_standalone: boolean;
  prerequisites: string[];
  created_at: string;
}

interface RawSectionDelivery {
  delivery_id: string;
  section_id: string;
  user_id: string;
  lecture_script: string;
  delivered_at: string;
  duration_actual_minutes?: number;
  user_notes?: string;
  style_snapshot: Record<string, unknown>;
}

interface RawCoursePart {
  section_id: string;
  title: string;
  estimated_minutes: number;
  status: string;
  sections: RawCourseSection[];
  total_sections: number;
  completed_sections: number;
}

interface RawCourseOutline {
  course_id: string;
  title: string;
  original_query?: string;  // The prompt/query used to create the course
  parts: RawCoursePart[];  // Hierarchical structure
  sections: RawCourseSection[];  // Flat list (backward compatibility)
  total_sections: number;
  completed_sections: number;
  total_minutes: number;
  preferences?: {
    presentation_style?: string;
    depth?: string;
    pace?: string;
    additional_notes?: string;
  };
}

// Normalization functions
const normalizeCourse = (raw: RawCourse): Course => ({
  courseId: raw.course_id,
  userId: raw.user_id,
  title: raw.title,
  originalQuery: raw.original_query,
  estimatedHours: raw.estimated_hours,
  createdAt: raw.created_at,
  lastModified: raw.last_modified,
  preferences: {
    depth: raw.preferences.depth as CoursePreferences["depth"],
    presentationStyle: raw.preferences.presentation_style,
    pace: raw.preferences.pace as CoursePreferences["pace"],
    additionalNotes: raw.preferences.additional_notes,
  },
  status: raw.status as Course["status"],
});

const normalizeSection = (raw: RawCourseSection): CourseSection => ({
  sectionId: raw.section_id,
  courseId: raw.course_id,
  parentSectionId: raw.parent_section_id,
  orderIndex: raw.order_index,
  title: raw.title,
  learningObjectives: raw.learning_objectives,
  contentSummary: raw.content_summary,
  estimatedMinutes: raw.estimated_minutes,
  chunkIds: raw.chunk_ids,
  status: raw.status as CourseSection["status"],
  completedAt: raw.completed_at,
  canStandalone: raw.can_standalone,
  prerequisites: raw.prerequisites,
  createdAt: raw.created_at,
});

const normalizeDelivery = (raw: RawSectionDelivery): SectionDelivery => ({
  deliveryId: raw.delivery_id,
  sectionId: raw.section_id,
  userId: raw.user_id,
  lectureScript: raw.lecture_script,
  deliveredAt: raw.delivered_at,
  durationActualMinutes: raw.duration_actual_minutes,
  userNotes: raw.user_notes,
  styleSnapshot: raw.style_snapshot,
});

const normalizePart = (raw: RawCoursePart): CoursePart => ({
  sectionId: raw.section_id,
  title: raw.title,
  estimatedMinutes: raw.estimated_minutes,
  status: raw.status as SectionStatus,
  sections: raw.sections.map(normalizeSection),
  totalSections: raw.total_sections,
  completedSections: raw.completed_sections,
});

const normalizeOutline = (raw: RawCourseOutline): CourseOutline => ({
  courseId: raw.course_id,
  title: raw.title,
  originalQuery: raw.original_query,
  preferences: raw.preferences,
  parts: raw.parts ? raw.parts.map(normalizePart) : [],  // Hierarchical structure
  sections: raw.sections.map(normalizeSection),  // Flat list for backward compatibility
  totalSections: raw.total_sections,
  completedSections: raw.completed_sections,
  totalMinutes: raw.total_minutes,
});

// API functions
export const listCourses = async (): Promise<Array<{
  courseId: string;
  title: string;
  estimatedHours: number;
  status: string;
  createdAt?: string;
}>> => {
  const response = await apiClient.get<Array<{
    courseId: string;
    course_id: string;
    title: string;
    estimatedHours: number;
    status: string;
    createdAt?: string;
  }>>("/courses");
  return response.data.map(course => ({
    courseId: course.courseId || course.course_id,
    title: course.title,
    estimatedHours: course.estimatedHours,
    status: course.status,
    createdAt: course.createdAt,
  }));
};

export const deleteCourse = async (courseId: string): Promise<void> => {
  await apiClient.delete(`/courses/${courseId}`);
};

export const createCourse = async (
  request: CreateCourseRequest,
): Promise<CreateCourseResponse> => {
  const response = await apiClient.post<CreateCourseResponse>("/courses/create", {
    query: request.query,
    time_hours: request.timeHours,
    // Note: preferences removed - style selected at lecture generation time
  });
  return response.data;
};

export const getCourseOutline = async (courseId: string): Promise<CourseOutline> => {
  const response = await apiClient.get<RawCourseOutline>(`/courses/${courseId}/outline`, {
    timeout: 10000, // 10 second timeout for outline (should be fast, but has more data than status)
  });
  return normalizeOutline(response.data);
};

export const getNextSection = async (courseId: string): Promise<{
  section?: {
    sectionId: string;
    title: string;
    estimatedMinutes: number;
  };
  message: string;
}> => {
  const response = await apiClient.post<{
    section?: {
      section_id: string;
      title: string;
      estimated_minutes: number;
    };
    message: string;
  }>(`/courses/${courseId}/next`);
  
  return {
    section: response.data.section ? {
      sectionId: response.data.section.section_id,
      title: response.data.section.title,
      estimatedMinutes: response.data.section.estimated_minutes,
    } : undefined,
    message: response.data.message,
  };
};

export const getStandaloneSection = async (
  courseId: string,
  request: StandaloneSectionRequest,
): Promise<{
  section?: {
    sectionId: string;
    title: string;
  };
  message: string;
}> => {
  const response = await apiClient.post<{
    section?: {
      section_id: string;
      title: string;
    };
    message: string;
  }>(`/courses/${courseId}/standalone`, {
    available_minutes: request.availableMinutes,
  });
  
  return {
    section: response.data.section ? {
      sectionId: response.data.section.section_id,
      title: response.data.section.title,
    } : undefined,
    message: response.data.message,
  };
};

export const regenerateSectionLecture = async (
  sectionId: string,
  presentationStyle: string
): Promise<void> => {
  const response = await apiClient.post(
    `/courses/section/${sectionId}/regenerate`,
    { presentation_style: presentationStyle },
    { timeout: 600000 } // 10 minutes for regeneration
  );
  // No return value needed, just wait for completion
};

export const getGenerationStatus = async (sectionId: string): Promise<{
  section_id: string;
  phase: "objectives" | "refining" | "complete" | "not_started";
  covered_objectives: number;
  total_objectives: number;
  progress_percent: number;
  current_step: string;
}> => {
  try {
    const response = await apiClient.get<{
      section_id: string;
      phase: string;
      covered_objectives: number;
      total_objectives: number;
      progress_percent: number;
      current_step: string;
    }>(`/courses/section/${sectionId}/generation-status`, {
      timeout: 30000, // 30 second timeout - server responds in <1ms but network/HTTP layer may be slow
      // Note: This endpoint should be very fast (in-memory lookup), so if it truly times out
      // after 30s, there's likely a network issue, not a server problem
    });
    
    // Verify the section ID matches (for debugging)
    if (response.data.section_id && response.data.section_id !== sectionId) {
      console.warn(`Status section ID mismatch! Requested: ${sectionId}, Got: ${response.data.section_id}`);
    }
    
    const result = {
      section_id: response.data.section_id || sectionId,
      phase: response.data.phase as "objectives" | "refining" | "complete" | "not_started",
      covered_objectives: response.data.covered_objectives,
      total_objectives: response.data.total_objectives,
      progress_percent: response.data.progress_percent,
      current_step: response.data.current_step,
    };
    
    return result;
  } catch (error: any) {
    console.error(`Status API call failed for section ${sectionId}:`, error);
    throw error;
  }
};

export const getSectionLecture = async (sectionId: string): Promise<{
  sectionId: string;
  lectureScript: string;
  estimatedMinutes: number;
  deliveryId?: string;
  figures: Array<{
    figure_id: string;
    chunk_id: string;
    caption: string;
    description: string;
    page: number;
    book_id: string;
    chapter_number?: number;
    similarity: number;
    explanation?: string;
  }>;
}> => {
  try {
    // Lecture generation can take several minutes, so use a longer timeout
    const response = await apiClient.get<{
      section_id: string;
      lecture_script: string;
      estimated_minutes: number;
      delivery_id?: string;
      figures?: Array<{
        figure_id: string;
        chunk_id: string;
        caption: string;
        description: string;
        page: number;
        book_id: string;
        chapter_number?: number;
        similarity: number;
        explanation?: string;
      }>;
      qa_history?: Array<{
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
      }>;
    }>(`/courses/section/${sectionId}/lecture`, {
      timeout: 30 * 1000, // 30 second timeout - should be fast now (no blocking)
      validateStatus: (status) => status === 200 || status === 202, // Accept 202 Accepted
    });
    
    // Handle 202 Accepted (generation in progress)
    if (response.status === 202) {
      // Generation is in progress - throw a specific error that the UI can handle
      const error: any = new Error("Lecture generation is in progress");
      error.response = {
        status: 202,
        data: response.data,
      };
      error.isGenerationInProgress = true;
      throw error;
    }
    
    // 200 OK - lecture is ready
    return {
      sectionId: response.data.section_id,
      lectureScript: response.data.lecture_script,
      figures: response.data.figures || [],
      estimatedMinutes: response.data.estimated_minutes,
      deliveryId: response.data.delivery_id,
      qaHistory: response.data.qa_history || [],
    };
  } catch (error: any) {
    // If it's our 202 Accepted marker, re-throw it
    if (error.isGenerationInProgress) {
      throw error;
    }
    // Otherwise, let the error propagate (404, 500, etc.)
    throw error;
  }
};

export const pauseSectionForQA = async (
  sectionId: string,
  lecturePositionSeconds: number,
): Promise<{
  message: string;
  qaSessionId?: string;
}> => {
  const response = await apiClient.post<{
    message: string;
    qa_session_id?: string;
  }>(`/courses/section/${sectionId}/pause-qa`, {
    lecture_position_seconds: lecturePositionSeconds,
  });
  
  return {
    message: response.data.message,
    qaSessionId: response.data.qa_session_id,
  };
};

export const askQAQuestion = async (
  sectionId: string,
  question: string,
): Promise<{
  message: string;
}> => {
  const response = await apiClient.post<{
    message: string;
  }>(`/courses/section/${sectionId}/qa-question`, {
    question,
  });
  
  return {
    message: response.data.message,
  };
};

/**
 * Get audio blob URL for a section lecture.
 * Fetches audio with authentication and returns a blob URL for the audio element.
 * 
 * For streaming audio (generates on-demand), use getSectionAudioStreamUrl instead.
 */
export const getSectionAudioUrl = async (sectionId: string): Promise<string> => {
  try {
    const response = await apiClient.get(
      `/courses/section/${sectionId}/audio`,
      { responseType: 'blob' }
    );
    
    // Create blob URL from audio data
    const blob = new Blob([response.data], { type: 'audio/mpeg' });
    const blobUrl = URL.createObjectURL(blob);
    return blobUrl;
  } catch (err: any) {
    console.error("Failed to fetch audio:", err);
    throw err;
  }
};

/**
 * Get streaming audio URL for a section lecture.
 * Returns a URL that the audio element can use directly for streaming playback.
 * The audio will start playing as soon as enough bytes are buffered (true streaming).
 */
export interface ChunkMetadata {
  text: string;
  start_proportion: number;  // 0.0 to 1.0 - proportion of total audio duration
  end_proportion: number;    // 0.0 to 1.0 - proportion of total audio duration
}

export interface LectureMetadata {
  chunks: ChunkMetadata[];
}

export const getSectionLectureMetadata = async (sectionId: string): Promise<LectureMetadata> => {
  // Use API_URL from client.ts which uses VITE_API_GATEWAY_URL
  const response = await apiClient.get<LectureMetadata>(
    `/courses/section/${sectionId}/lecture-metadata`
  );
  
  return response.data;
};

import { API_URL } from "./client";

export const getSectionAudioChunkUrl = (sectionId: string, chunkIndex: number): string => {
  // Get token from Amplify session (not localStorage)
  // Note: For streaming URLs, we may need to pass token via query param
  // For now, rely on Amplify's automatic token injection via apiClient
  return `${API_URL}/courses/section/${sectionId}/audio-chunk/${chunkIndex}`;
};

export const getSectionAudioStreamUrl = (sectionId: string): string => {
  // Return URL - Amplify will handle authentication via apiClient
  // The backend will validate the token from Authorization header
  return `${API_URL}/courses/section/${sectionId}/audio-stream`;
};

/**
 * Generate audio for a section lecture on-demand with streaming progress.
 * Uses Server-Sent Events (SSE) to receive progress updates as chunks are generated.
 * 
 * @param sectionId - The section ID
 * @param onProgress - Optional callback for progress updates (chunks_generated, total_chunks, message)
 * @returns Promise that resolves when audio generation is complete
 */
export const generateSectionAudioStream = async (
  sectionId: string,
  onProgress?: (progress: {
    message: string;
    chunks_generated?: number;
    total_chunks?: number;
    total_bytes?: number;
    complete?: boolean;
    error?: string;
  }) => void,
  abortSignal?: AbortSignal
): Promise<{
  message: string;
  audio_available: boolean;
  chunks_generated?: number;
  total_chunks?: number;
  total_bytes?: number;
}> => {
  // Use API_URL from client.ts which uses VITE_API_GATEWAY_URL
  const apiUrl = import.meta.env.VITE_API_GATEWAY_URL || API_URL;
  
  return new Promise((resolve, reject) => {
    // EventSource doesn't support POST or custom headers, so we use fetch with SSE parsing
    fetch(`${apiUrl}/courses/section/${sectionId}/generate-audio-stream`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'text/event-stream',
      },
      credentials: 'include',
      signal: abortSignal, // Support cancellation
    })
      .then(async (response) => {
        if (!response.ok) {
          const error = await response.json().catch(() => ({ error: 'Failed to start audio generation' }));
          reject(new Error(error.error || `HTTP ${response.status}`));
          return;
        }
        
        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        
        if (!reader) {
          reject(new Error('Response body is not readable'));
          return;
        }
        
        let buffer = '';
        let finalResult: any = null;
        
        while (true) {
          const { done, value } = await reader.read();
          
          if (done) {
            break;
          }
          
          buffer += decoder.decode(value, { stream: true });
          
          // Process complete SSE messages
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep incomplete line in buffer
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                
                if (data.error) {
                  reject(new Error(data.error));
                  return;
                }
                
                if (onProgress) {
                  onProgress(data);
                }
                
                if (data.complete) {
                  finalResult = {
                    message: data.message,
                    audio_available: data.audio_available || true,
                    chunks_generated: data.chunks_generated,
                    total_chunks: data.total_chunks,
                    total_bytes: data.total_bytes,
                  };
                }
              } catch (e) {
                console.error('Failed to parse SSE data:', e, line);
              }
            }
          }
        }
        
        if (finalResult) {
          resolve(finalResult);
        } else {
          reject(new Error('Audio generation did not complete'));
        }
      })
      .catch((err) => {
        reject(err);
      });
  });
};

/**
 * Generate audio for a section lecture on-demand (non-streaming, for backward compatibility).
 * This is called when the user wants audio for a lecture that doesn't have it yet.
 */
export const generateSectionAudio = async (sectionId: string): Promise<{
  message: string;
  audio_available: boolean;
  chunks_generated?: number;
  total_chunks?: number;
  total_bytes?: number;
}> => {
  // Use a longer timeout for audio generation (can take 30-60 seconds for multiple chunks)
  const response = await apiClient.post<{
    message: string;
    audio_available: boolean;
    chunks_generated?: number;
    total_chunks?: number;
    total_bytes?: number;
  }>(`/courses/section/${sectionId}/generate-audio`, {}, {
    timeout: 120000, // 2 minutes timeout for long audio generation
  });
  
  return {
    message: response.data.message,
    audio_available: response.data.audio_available,
    chunks_generated: response.data.chunks_generated,
    total_chunks: response.data.total_chunks,
    total_bytes: response.data.total_bytes,
  };
};

export const resumeLecture = async (sectionId: string): Promise<{
  message: string;
}> => {
  const response = await apiClient.post<{
    message: string;
  }>(`/courses/section/${sectionId}/resume`);
  
  return {
    message: response.data.message,
  };
};

export const completeSection = async (sectionId: string): Promise<{
  message: string;
}> => {
  const response = await apiClient.post<{
    message: string;
  }>(`/courses/section/${sectionId}/complete`);
  
  return {
    message: response.data.message,
  };
};

/**
 * Types for lecture Q&A
 */
export interface Citation {
  chunk_id: string;
  book_id: string;
  book_title: string;
  page_number?: number;
  section_title?: string;
  text: string;
  relevance_score: number;
}

export interface LectureQuestionRequest {
  question: string;
  paragraph_index: number;
  lecture_delivered: string;
  lecture_remaining: string;
  is_follow_up: boolean;
  previous_qa_context?: string;
}

export interface LectureQuestionResponse {
  enhanced_question: string;
  answer: string;
  citations: Citation[];
  sources_used: string[];
}

/**
 * Submit a question during lecture with full context.
 * 
 * The system will:
 * 1. Enhance the question with lecture context
 * 2. Search for relevant textbook passages
 * 3. Generate an answer maintaining the lecture persona
 * 
 * @param sectionId - The section ID
 * @param request - Question and lecture context
 * @returns Enhanced question, answer with citations, and sources
 */
export const submitLectureQuestion = async (
  sectionId: string,
  request: LectureQuestionRequest
): Promise<LectureQuestionResponse> => {
  const response = await apiClient.post<LectureQuestionResponse>(
    `/courses/section/${sectionId}/lecture-question`,
    request
  );
  
  return response.data;
};

/**
 * Revise a course outline based on user request.
 * 
 * This allows users to modify the remaining (uncompleted) sections
 * of a course outline. Completed sections are immutable.
 * 
 * @param courseId - The course ID
 * @param revisionRequest - Natural language request for changes (e.g., "add a section on tax implications")
 * @returns Success message
 */
export const reviseCourseOutline = async (
  courseId: string,
  revisionRequest: string
): Promise<{
  message: string;
  success: boolean;
}> => {
  const response = await apiClient.post<{
    message: string;
    success: boolean;
  }>(`/courses/${courseId}/revise`, {
    revision_request: revisionRequest,
  }, {
    timeout: 120000, // 2 minutes timeout for revision (can take time for LLM)
  });
  
  return response.data;
};

