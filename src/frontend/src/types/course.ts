export type CourseDepth = "overview" | "balanced" | "technical" | "expert";
export type CoursePace = "quick" | "moderate" | "thorough";
export type CourseStatus = "active" | "completed" | "archived";
export type SectionStatus = "not_started" | "in_progress" | "completed";
export type CourseDeliveryMode = "lecture" | "qa";

export interface CoursePreferences {
  depth: CourseDepth;
  presentationStyle: string;  // Can be simple keyword or detailed description
  pace: CoursePace;
  additionalNotes?: string;
}

export interface Course {
  courseId: string;
  userId: string;
  title: string;
  originalQuery: string;
  estimatedHours: number;
  createdAt: string;
  lastModified: string;
  preferences: CoursePreferences;
  status: CourseStatus;
}

export interface CourseSection {
  sectionId: string;
  courseId: string;
  parentSectionId?: string;
  orderIndex: number;
  title: string;
  learningObjectives: string[];
  contentSummary?: string;
  estimatedMinutes: number;
  chunkIds: string[];
  status: SectionStatus;
  completedAt?: string;
  canStandalone: boolean;
  prerequisites: string[];
  createdAt: string;
}

export interface SectionDelivery {
  deliveryId: string;
  sectionId: string;
  userId: string;
  lectureScript: string;
  deliveredAt: string;
  durationActualMinutes?: number;
  userNotes?: string;
  styleSnapshot: Record<string, unknown>;
}

export interface QAMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

export interface QASession {
  qaSessionId: string;
  sectionId: string;
  deliveryId?: string;
  userId: string;
  startedAt: string;
  endedAt?: string;
  lecturePositionSeconds?: number;
  qaMessages: QAMessage[];
  contextChunks: string[];
  metadata: Record<string, unknown>;
}

export interface CoursePart {
  sectionId: string;
  title: string;
  estimatedMinutes: number;
  status: SectionStatus;
  sections: CourseSection[];  // Child sections
  totalSections: number;
  completedSections: number;
}

export interface CourseOutline {
  courseId: string;
  title: string;
  originalQuery?: string;  // The prompt/query used to create the course
  parts: CoursePart[];  // Hierarchical: parts contain sections
  sections: CourseSection[];  // Flat list (for backward compatibility)
  totalSections: number;  // Total child sections (not counting parts)
  completedSections: number;
  totalMinutes: number;
  preferences?: {
    presentation_style?: string;
    depth?: string;
    pace?: string;
    additional_notes?: string;
  };
}

export interface CreateCourseRequest {
  query: string;  // User's course request (can include context like "I am a veteran investment banker...")
  timeHours: number;  // Target course duration in hours
  // Note: preferences removed - style selected at lecture generation time
}

export interface CreateCourseResponse {
  courseId: string;
  title: string;
  message: string;
  pending?: boolean;
}

export interface StandaloneSectionRequest {
  availableMinutes: number;
}

