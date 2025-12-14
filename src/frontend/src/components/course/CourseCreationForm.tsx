import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createCourse } from "../../api/courses";

interface CourseCreationFormProps {
  onCourseCreated?: (courseId: string) => void;
}

export const CourseCreationForm = ({ onCourseCreated }: CourseCreationFormProps) => {
  const [query, setQuery] = useState("");
  const [timeHours, setTimeHours] = useState(2.0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");
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

    // Simulate progress updates (since course creation is async)
    const progressMessages = [
      "Analyzing your request and finding relevant material...",
      "Searching knowledge base for relevant content...",
      "Finding relevant books and summaries...",
      "Planning course structure...",
      "Generating course sections...",
      "Reviewing and finalizing course outline...",
    ];

    let messageIndex = 0;
    const progressInterval = setInterval(() => {
      if (messageIndex < progressMessages.length - 1) {
        messageIndex++;
        setStatusMessage(progressMessages[messageIndex]);
      }
    }, 8000); // Update message every 8 seconds

    try {
      const result = await createCourse({
        query: query.trim(),
        timeHours,
      });

      clearInterval(progressInterval);
      setStatusMessage("Course created successfully!");

      const courseId = result.courseId || (result as any).course_id;
      if (!courseId) {
        setError("Course created but no course ID returned");
        return;
      }
      
      // Small delay to show success message
      await new Promise(resolve => setTimeout(resolve, 500));
      
      if (onCourseCreated) {
        onCourseCreated(courseId);
      } else {
        navigate(`/courses/${courseId}`);
      }
    } catch (err) {
      clearInterval(progressInterval);
      console.error("Failed to create course:", err);
      setError(err instanceof Error ? err.message : "Failed to create course");
      setStatusMessage("");
    } finally {
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
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <div className="inline-block animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
              <p className="text-sm text-gray-600">{statusMessage || "Creating course..."}</p>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                style={{
                  width: loading ? "100%" : "0%",
                  animation: loading ? "pulse 2s ease-in-out infinite" : "none",
                }}
              />
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

