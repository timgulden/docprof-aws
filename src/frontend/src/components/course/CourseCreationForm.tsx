import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createCourse, getCourseStatus } from "../../api/courses";

interface CourseCreationFormProps {
  onCourseCreated?: (courseId: string) => void;
}

// Ordered phases for progress bar
const PHASES = [
  { key: "initializing", label: "Analyzing" },
  { key: "searching_books", label: "Searching" },
  { key: "generating_sections", label: "Planning" },
  { key: "reviewing_outline", label: "Reviewing" },
  { key: "storing_sections", label: "Saving" },
  { key: "complete", label: "Complete" },
] as const;

type Phase = typeof PHASES[number]["key"];

export const CourseCreationForm = ({ onCourseCreated }: CourseCreationFormProps) => {
  const [query, setQuery] = useState("");
  const [timeHours, setTimeHours] = useState(2.0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [currentPhase, setCurrentPhase] = useState<Phase>("initializing");
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) {
      setError("Please enter a course topic");
      return;
    }

    setLoading(true);
    setError(null);
    setStatusMessage("Analyzing your request and finding relevant material...");

    try {
      const result = await createCourse({
        query: query.trim(),
        timeHours,
      });

      const courseId = result.courseId || (result as any).course_id;
      if (!courseId) {
        setError("Course created but no course ID returned");
        return;
      }
      
      // Poll for status updates
      const pollInterval = setInterval(async () => {
        try {
          const status = await getCourseStatus(courseId);
          
          // Update phase for progress bar
          setCurrentPhase(status.phase as Phase);
          
          // Use backend message if available
          setStatusMessage(status.progress?.message || status.message || "Processing...");
          
          if (status.status === "complete" && status.phase === "complete") {
            clearInterval(pollInterval);
            setStatusMessage(status.progress?.message || "Course created successfully!");
            
            // Small delay to show success message
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            if (onCourseCreated) {
              onCourseCreated(courseId);
            } else {
              navigate(`/courses/${courseId}`);
            }
          } else if (status.status === "error") {
            clearInterval(pollInterval);
            setError(status.error || "Course creation failed");
            setStatusMessage("");
            setLoading(false);
          }
        } catch (err) {
          console.error("Failed to poll status:", err);
          // Don't stop polling on individual errors, but log them
        }
      }, 2000); // Poll every 2 seconds
      
      // Safety timeout: stop polling after 2 minutes
      setTimeout(() => {
        clearInterval(pollInterval);
        if (loading) {
          setError("Course creation timed out. Please refresh and check your courses.");
          setStatusMessage("");
          setLoading(false);
        }
      }, 120000);
      
    } catch (err) {
      console.error("Failed to create course:", err);
      setError(err instanceof Error ? err.message : "Failed to create course");
      setStatusMessage("");
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-6 bg-white rounded-lg shadow">
      <h2 className="text-2xl font-bold mb-6">Create New Course</h2>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Course Query */}
        <div>
          <label htmlFor="query" className="block text-sm font-medium text-gray-700 mb-2">
            What would you like to learn?
          </label>
          <textarea
            id="query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g., I want to learn LBO modeling fundamentals. I am a veteran investment banker looking to freshen up my technical knowledge."
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            rows={4}
            disabled={loading}
          />
          <p className="mt-1 text-sm text-gray-500">
            Include any relevant context about your background or specific needs in your request.
          </p>
        </div>

        {/* Time Hours */}
        <div>
          <label htmlFor="timeHours" className="block text-sm font-medium text-gray-700 mb-2">
            How long do you have? (hours)
          </label>
          <input
            type="number"
            id="timeHours"
            min="0.5"
            max="12"
            step="0.5"
            value={timeHours}
            onChange={(e) => setTimeHours(parseFloat(e.target.value) || 2.0)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            disabled={loading}
          />
          <p className="mt-1 text-sm text-gray-500">
            {timeHours <= 1 
              ? "Short course (overview level)" 
              : timeHours <= 3 
              ? "Medium course (balanced depth)" 
              : timeHours <= 6
              ? "Long course (technical depth)"
              : "Extended course (expert level)"}
          </p>
          <p className="mt-1 text-xs text-gray-500">
            Note: Course depth is automatically determined by the time you specify. You can select your preferred style (formal, conversational, casual, podcast) when you start the first lecture.
          </p>
        </div>

        {/* Progress Indicator */}
        {loading && (
          <div className="space-y-4">
            {/* Phase Progress Bar */}
            <div className="flex items-center justify-between">
              {PHASES.map((phase, index) => {
                const phaseIndex = PHASES.findIndex(p => p.key === currentPhase);
                const isComplete = index < phaseIndex;
                const isCurrent = index === phaseIndex;
                const isPending = index > phaseIndex;
                
                return (
                  <div key={phase.key} className="flex flex-col items-center flex-1">
                    {/* Phase dot */}
                    <div className="flex items-center w-full">
                      {index > 0 && (
                        <div 
                          className={`flex-1 h-1 ${isComplete ? 'bg-blue-600' : 'bg-gray-200'}`}
                        />
                      )}
                      <div 
                        className={`w-4 h-4 rounded-full flex items-center justify-center text-xs font-bold
                          ${isComplete ? 'bg-blue-600 text-white' : ''}
                          ${isCurrent ? 'bg-blue-600 text-white animate-pulse' : ''}
                          ${isPending ? 'bg-gray-200 text-gray-400' : ''}
                        `}
                      >
                        {isComplete ? '✓' : index + 1}
                      </div>
                      {index < PHASES.length - 1 && (
                        <div 
                          className={`flex-1 h-1 ${isComplete ? 'bg-blue-600' : 'bg-gray-200'}`}
                        />
                      )}
                    </div>
                    {/* Phase label */}
                    <span className={`text-xs mt-1 ${isCurrent ? 'text-blue-600 font-semibold' : 'text-gray-500'}`}>
                      {phase.label}
                    </span>
                  </div>
                );
              })}
            </div>
            
            {/* Status Message */}
            <div className="flex items-center justify-center gap-3 py-2 px-4 bg-blue-50 rounded-lg">
              <div className="inline-block animate-spin rounded-full h-4 w-4 border-2 border-blue-600 border-t-transparent"></div>
              <p className="text-sm text-blue-700">{statusMessage || "Creating course..."}</p>
            </div>
            
            <p className="text-xs text-gray-500 text-center">
              This usually takes 30-60 seconds. Please wait...
            </p>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? "Creating Course..." : "Create Course"}
        </button>
      </form>
    </div>
  );
};

