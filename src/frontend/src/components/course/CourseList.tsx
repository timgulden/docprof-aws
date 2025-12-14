import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { listCourses, deleteCourse } from "../../api/courses";
import { Plus, Trash2 } from "lucide-react";

export const CourseList = () => {
  const [courses, setCourses] = useState<Array<{
    courseId: string;
    title: string;
    estimatedHours: number;
    status: string;
    createdAt?: string;
  }>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingCourseId, setDeletingCourseId] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const loadCourses = async () => {
      try {
        setLoading(true);
        const data = await listCourses();
        setCourses(data);
      } catch (err) {
        console.error("Failed to load courses:", err);
        setError(err instanceof Error ? err.message : "Failed to load courses");
      } finally {
        setLoading(false);
      }
    };

    loadCourses();
  }, []);

  const handleDeleteCourse = async (courseId: string, courseTitle: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent navigation when clicking delete button
    
    if (!window.confirm(`Are you sure you want to delete "${courseTitle}"? This will permanently delete the course, all sections, lectures, audio, and Q&A. This action cannot be undone.`)) {
      return;
    }
    
    try {
      setDeletingCourseId(courseId);
      await deleteCourse(courseId);
      // Remove the course from the list
      setCourses(courses.filter(c => c.courseId !== courseId));
    } catch (err) {
      console.error("Failed to delete course:", err);
      setError(err instanceof Error ? err.message : "Failed to delete course");
    } finally {
      setDeletingCourseId(null);
    }
  };

  if (loading) {
    return (
      <div className="p-6 text-center">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <p className="mt-2 text-gray-600">Loading courses...</p>
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

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold">My Courses</h1>
        <button
          onClick={() => navigate("/courses/new")}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <Plus className="w-5 h-5" />
          New Course
        </button>
      </div>

      {courses.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
          <p className="text-gray-600 mb-4">You haven't created any courses yet.</p>
          <button
            onClick={() => navigate("/courses/new")}
            className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Create Your First Course
          </button>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {courses.map((course) => (
            <div
              key={course.courseId}
              className="p-6 bg-white rounded-lg shadow hover:shadow-lg transition-shadow border border-gray-200 flex flex-col"
            >
              <div
                onClick={() => navigate(`/courses/${course.courseId}`)}
                className="cursor-pointer flex-1 flex flex-col"
              >
                <h2 className="text-xl font-semibold mb-2">{course.title}</h2>
                <div className="text-sm text-gray-600 space-y-1">
                  <p>Estimated: {course.estimatedHours} hours</p>
                  {course.createdAt && (
                    <p className="text-xs text-gray-500">
                      Created: {new Date(course.createdAt).toLocaleDateString()}
                    </p>
                  )}
                </div>
                <div className="mt-auto pt-4 flex items-center justify-between">
                  <span className={`inline-block px-2 py-1 text-xs rounded ${
                    course.status === "active" 
                      ? "bg-green-100 text-green-800" 
                      : "bg-gray-100 text-gray-800"
                  }`}>
                    {course.status}
                  </span>
                  <button
                    onClick={(e) => handleDeleteCourse(course.courseId, course.title, e)}
                    disabled={deletingCourseId === course.courseId}
                    className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    title="Delete course"
                    aria-label={`Delete ${course.title}`}
                  >
                    {deletingCourseId === course.courseId ? (
                      <div className="w-4 h-4 border-2 border-red-600 border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <Trash2 className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

