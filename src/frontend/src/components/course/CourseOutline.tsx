import { useEffect, useState } from "react";
import { CheckCircle2, Circle, PlayCircle, RotateCcw, Edit3 } from "lucide-react";
import { getCourseOutline, regenerateSectionLecture, reviseCourseOutline } from "../../api/courses";
import type { CourseOutline as CourseOutlineType, CourseSection } from "../../types/course";

interface CourseOutlineProps {
  courseId: string;
  onSectionSelect?: (sectionId: string) => void;
  presentationStyle?: string;
}

export const CourseOutline = ({ courseId, onSectionSelect, presentationStyle = "conversational" }: CourseOutlineProps) => {
  const [outline, setOutline] = useState<CourseOutlineType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [regenerating, setRegenerating] = useState<Set<string>>(new Set());
  const [showRevisionModal, setShowRevisionModal] = useState(false);
  const [revisionRequest, setRevisionRequest] = useState("");
  const [revising, setRevising] = useState(false);
  const [revisionStatus, setRevisionStatus] = useState<string>("");

  const handleRegenerate = async (sectionId: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent section selection
    try {
      setRegenerating(prev => new Set(prev).add(sectionId));
      // Start regeneration (returns immediately, runs in background)
      regenerateSectionLecture(sectionId, presentationStyle).catch((err) => {
        console.error("Failed to start regeneration:", err);
        // Don't show alert here - let SectionPlayer handle status polling
      });
      // Navigate to section player immediately to show progress screen
      onSectionSelect?.(sectionId);
    } catch (err) {
      console.error("Failed to regenerate lecture:", err);
      alert(err instanceof Error ? err.message : "Failed to regenerate lecture");
    } finally {
      // Clear regenerating state after a short delay to allow navigation
      setTimeout(() => {
        setRegenerating(prev => {
          const next = new Set(prev);
          next.delete(sectionId);
          return next;
        });
      }, 100);
    }
  };

  const handleReviseOutline = async () => {
    if (!revisionRequest.trim()) {
      alert("Please enter a revision request");
      return;
    }

    try {
      setRevising(true);
      setRevisionStatus("Analyzing your revision request...");
      
      // Show progress updates similar to course creation
      const progressMessages = [
        "Analyzing your revision request...",
        "Searching knowledge base for relevant content...",
        "Finding relevant books and summaries...",
        "Regenerating course structure...",
        "Generating revised course sections...",
        "Reviewing and finalizing revised outline...",
      ];

      let messageIndex = 0;
      const progressInterval = setInterval(() => {
        if (messageIndex < progressMessages.length - 1) {
          messageIndex++;
          setRevisionStatus(progressMessages[messageIndex]);
        }
      }, 6000); // Update message every 6 seconds

      const result = await reviseCourseOutline(courseId, revisionRequest);
      
      clearInterval(progressInterval);
      
      if (result.success) {
        setRevisionStatus("Revision complete! Loading updated outline...");
        
        // Reload outline to show changes (same as course creation flow)
        const data = await getCourseOutline(courseId);
        setOutline(data);
        
        // Small delay to show completion message
        await new Promise(resolve => setTimeout(resolve, 500));
        
        setShowRevisionModal(false);
        setRevisionRequest("");
        setRevisionStatus("");
        // No alert - just silently update the UI like course creation does
      } else {
        clearInterval(progressInterval);
        setRevisionStatus("");
        alert(result.message || "Failed to revise outline");
      }
    } catch (err) {
      console.error("Failed to revise outline:", err);
      setRevisionStatus("");
      alert(err instanceof Error ? err.message : "Failed to revise outline");
    } finally {
      setRevising(false);
    }
  };

  useEffect(() => {
    const loadOutline = async () => {
      try {
        setLoading(true);
        const data = await getCourseOutline(courseId);
        setOutline(data);
      } catch (err) {
        console.error("Failed to load course outline:", err);
        setError(err instanceof Error ? err.message : "Failed to load outline");
      } finally {
        setLoading(false);
      }
    };

    loadOutline();
  }, [courseId]);

  const getStatusIcon = (status: CourseSection["status"]) => {
    switch (status) {
      case "completed":
        return <CheckCircle2 className="w-5 h-5 text-green-600" />;
      case "in_progress":
        return <PlayCircle className="w-5 h-5 text-blue-600" />;
      default:
        return <Circle className="w-5 h-5 text-gray-400" />;
    }
  };

  const getStatusColor = (status: CourseSection["status"]) => {
    switch (status) {
      case "completed":
        return "text-green-700 bg-green-50 border-green-200";
      case "in_progress":
        return "text-blue-700 bg-blue-50 border-blue-200";
      default:
        return "text-gray-700 bg-gray-50 border-gray-200";
    }
  };

  if (loading) {
    return (
      <div className="p-6 text-center">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <p className="mt-2 text-gray-600">Loading course outline...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-md">
        <p className="text-red-700">Error: {error}</p>
      </div>
    );
  }

  if (!outline) {
    return (
      <div className="p-6 text-center text-gray-500">
        No outline available
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6 flex items-end justify-between">
        <div className="flex-1">
          <h2 className="text-lg font-semibold text-gray-700 mb-2">Course Objective:</h2>
          {outline.originalQuery ? (
            <p className="text-gray-900 text-base leading-relaxed">{outline.originalQuery}</p>
          ) : (
            <p className="text-gray-500 text-sm italic">Course objective not available</p>
          )}
        </div>
        <button
          onClick={() => setShowRevisionModal(true)}
          className="ml-4 flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          title="Revise course outline"
        >
          <Edit3 className="w-4 h-4" />
          <span>Revise</span>
        </button>
      </div>

      {/* Revision Modal */}
      {showRevisionModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
            <h3 className="text-xl font-semibold mb-4">Revise Course Outline</h3>
            <p className="text-sm text-gray-600 mb-4">
              Describe how you'd like to modify the course outline. Completed sections cannot be changed,
              but you can modify, add, or remove remaining sections.
            </p>
            <textarea
              value={revisionRequest}
              onChange={(e) => setRevisionRequest(e.target.value)}
              placeholder="e.g., 'Add a section on tax implications' or 'Make the remaining sections more technical'"
              className="w-full p-3 border border-gray-300 rounded-lg mb-4 min-h-[120px] focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={revising}
            />
            
            {/* Progress Indicator */}
            {revising && (
              <div className="mb-4 space-y-3">
                <div className="flex items-center gap-3">
                  <div className="inline-block animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
                  <p className="text-sm text-gray-600">{revisionStatus || "Revising outline..."}</p>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                    style={{
                      width: revising ? "100%" : "0%",
                      animation: revising ? "pulse 2s ease-in-out infinite" : "none",
                    }}
                  />
                </div>
                <p className="text-xs text-gray-500 text-center">
                  This usually takes 30-60 seconds. Please wait...
                </p>
              </div>
            )}
            
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => {
                  setShowRevisionModal(false);
                  setRevisionRequest("");
                }}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                disabled={revising}
              >
                Cancel
              </button>
              <button
                onClick={handleReviseOutline}
                disabled={revising || !revisionRequest.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {revising ? "Revising..." : "Revise Outline"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Hierarchical outline: Parts with nested sections */}
      <div className="space-y-6">
        {outline.parts.length > 0 ? (
          // Show hierarchical structure (parts → sections)
          outline.parts.map((part) => (
            <div key={part.sectionId} className="border border-gray-200 rounded-lg overflow-hidden">
              {/* Part header */}
              <div className="bg-gray-50 px-4 py-3 border-b border-gray-200">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-lg text-gray-900">{part.title}</h3>
                  <div className="flex items-center gap-3 text-sm text-gray-600">
                    <span>{part.totalSections} sections</span>
                    <span>•</span>
                    <span>{part.completedSections} completed</span>
                    <span>•</span>
                    <span>{Math.round(part.estimatedMinutes / 60 * 10) / 10} hours</span>
                  </div>
                </div>
              </div>
              
              {/* Sections within this part */}
              <div className="divide-y divide-gray-100">
                {part.sections.map((section) => (
                  <div
                    key={section.sectionId}
                    className={`px-4 py-3 cursor-pointer transition-colors hover:bg-gray-50 ${getStatusColor(section.status)}`}
                    onClick={() => onSectionSelect?.(section.sectionId)}
                  >
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5">{getStatusIcon(section.status)}</div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-medium text-base">{section.title}</h4>
                          <span className="text-xs px-2 py-0.5 bg-white rounded">
                            {section.estimatedMinutes} min
                          </span>
                          {section.canStandalone && (
                            <span className="text-xs px-2 py-0.5 bg-white rounded">
                              Standalone
                            </span>
                          )}
                          {(section.status === "completed" || section.status === "in_progress") && (
                            <button
                              onClick={(e) => handleRegenerate(section.sectionId, e)}
                              disabled={regenerating.has(section.sectionId)}
                              className="ml-auto flex items-center gap-1 px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 disabled:opacity-50 disabled:cursor-not-allowed"
                              title="Regenerate lecture with current style"
                            >
                              <RotateCcw className={`w-3 h-3 ${regenerating.has(section.sectionId) ? 'animate-spin' : ''}`} />
                              {regenerating.has(section.sectionId) ? 'Regenerating...' : 'Regenerate'}
                            </button>
                          )}
                        </div>
                        {section.learningObjectives.length > 0 && (
                          <ul className="text-sm text-gray-600 list-disc list-inside space-y-0.5 ml-4">
                            {section.learningObjectives.map((obj, idx) => (
                              <li key={idx}>{obj}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))
        ) : (
          // Fallback: flat structure (backward compatibility)
          <div className="space-y-3">
            {outline.sections.map((section) => (
              <div
                key={section.sectionId}
                className={`p-4 border rounded-lg cursor-pointer transition-colors hover:shadow-md ${getStatusColor(section.status)}`}
                onClick={() => onSectionSelect?.(section.sectionId)}
              >
                <div className="flex items-start gap-3">
                  <div className="mt-0.5">{getStatusIcon(section.status)}</div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-semibold text-lg">{section.title}</h3>
                      <span className="text-xs px-2 py-0.5 bg-white rounded">
                        {section.estimatedMinutes} min
                      </span>
                      {section.canStandalone && (
                        <span className="text-xs px-2 py-0.5 bg-white rounded">
                          Standalone
                        </span>
                      )}
                      {(section.status === "completed" || section.status === "in_progress") && (
                        <button
                          onClick={(e) => handleRegenerate(section.sectionId, e)}
                          disabled={regenerating.has(section.sectionId)}
                          className="ml-auto flex items-center gap-1 px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 disabled:opacity-50 disabled:cursor-not-allowed"
                          title="Regenerate lecture with current style"
                        >
                          <RotateCcw className={`w-3 h-3 ${regenerating.has(section.sectionId) ? 'animate-spin' : ''}`} />
                          {regenerating.has(section.sectionId) ? 'Regenerating...' : 'Regenerate'}
                        </button>
                      )}
                    </div>
                    {section.contentSummary && (
                      <p className="text-sm text-gray-600 mb-2">{section.contentSummary}</p>
                    )}
                    {section.learningObjectives.length > 0 && (
                      <ul className="text-sm text-gray-600 list-disc list-inside space-y-1">
                        {section.learningObjectives.map((obj, idx) => (
                          <li key={idx}>{obj}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

