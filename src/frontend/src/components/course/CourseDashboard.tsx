import { useState, useEffect } from "react";
import { Play } from "lucide-react";
import { getCourseOutline, getNextSection } from "../../api/courses";
import { CourseOutline } from "./CourseOutline";
import { SectionPlayer } from "./SectionPlayer";

interface CourseDashboardProps {
  courseId: string;
}

export const CourseDashboard = ({ courseId }: CourseDashboardProps) => {
  const [outline, setOutline] = useState<Awaited<ReturnType<typeof getCourseOutline>> | null>(null);
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null);
  const [presentationStyle, setPresentationStyle] = useState<string>("conversational");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadOutline = async () => {
      try {
        setLoading(true);
        const data = await getCourseOutline(courseId);
        setOutline(data);
        // Populate presentation style from course preferences if available
        if (data.preferences?.presentation_style) {
          setPresentationStyle(data.preferences.presentation_style);
        }
      } catch (err) {
        console.error("Failed to load course outline:", err);
        setError(err instanceof Error ? err.message : "Failed to load course");
      } finally {
        setLoading(false);
      }
    };

    loadOutline();
  }, [courseId]);

  const handleNextSection = async () => {
    try {
      const result = await getNextSection(courseId);
      if (result.section) {
        setSelectedSectionId(result.section.sectionId);
      }
    } catch (err) {
      console.error("Failed to get next section:", err);
      setError(err instanceof Error ? err.message : "Failed to get next section");
    }
  };

  const handleSectionSelect = (sectionId: string) => {
    setSelectedSectionId(sectionId);
  };

  const handleSectionComplete = () => {
    setSelectedSectionId(null);
    // Reload outline to show updated progress
    const reloadOutline = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await getCourseOutline(courseId);
        setOutline(data);
      } catch (err) {
        console.error("Failed to reload outline:", err);
        setError(err instanceof Error ? err.message : "Failed to reload course outline");
        // Don't clear outline on error - keep showing the previous data
      } finally {
        setLoading(false);
      }
    };
    reloadOutline();
  };

  if (loading) {
    return (
      <div className="p-6 text-center">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <p className="mt-2 text-gray-600">Loading course...</p>
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

  if (selectedSectionId) {
    const section = outline?.sections.find((s) => s.sectionId === selectedSectionId);
    return (
      <div className="h-full">
        <SectionPlayer
          sectionId={selectedSectionId}
          sectionTitle={section?.title}
          courseId={courseId}
          onComplete={handleSectionComplete}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header with Actions */}
      <div className="p-4 border-b bg-white">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">{outline?.title || "Course"}</h1>
            {outline && (
              <div className="mt-2 flex items-center gap-4 text-sm text-gray-600">
                <span>
                  {outline.parts.length > 0 
                    ? `${outline.parts.length} parts, ${outline.totalSections} sections`
                    : `${outline.totalSections} sections`}
                </span>
                <span>•</span>
                <span>{outline.completedSections} completed</span>
                <span>•</span>
                <span>{Math.round(outline.totalMinutes / 60 * 10) / 10} hours</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleNextSection}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <Play className="w-4 h-4" />
              Next Section
            </button>
          </div>
        </div>

        {/* Presentation Style Input */}
        <div className="mt-4 flex items-center gap-3">
          <label className="text-sm text-gray-600 whitespace-nowrap">Presentation Style:</label>
          <input
            type="text"
            value={presentationStyle}
            onChange={(e) => setPresentationStyle(e.target.value)}
            placeholder="conversational"
            className="flex-1 max-w-md px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <span className="text-xs text-gray-500">(e.g., "conversational", "formal", "podcast", or custom description)</span>
        </div>
      </div>

      {/* Course Outline */}
      <div className="flex-1 overflow-y-auto">
        {outline && (
          <CourseOutline
            courseId={courseId}
            onSectionSelect={handleSectionSelect}
            presentationStyle={presentationStyle}
          />
        )}
      </div>
    </div>
  );
};

