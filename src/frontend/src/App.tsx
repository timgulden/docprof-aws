import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "react-hot-toast";

import { Layout } from "./components/common/Layout";
import { ProtectedRoute } from "./components/common/ProtectedRoute";
import { LoginForm } from "./components/auth/LoginForm";
import { RegisterForm } from "./components/auth/RegisterForm";
import { VerificationForm } from "./components/auth/VerificationForm";
import { ChatInterface } from "./components/chat/ChatInterface";
import { LecturePlayer } from "./components/lecture/LecturePlayer";
import { QuizInterface } from "./components/quiz/QuizInterface";
import { CourseCreationForm } from "./components/course/CourseCreationForm";
import { CourseDashboard } from "./components/course/CourseDashboard";
import { CourseList } from "./components/course/CourseList";
import { SourcesView } from "./components/sources/SourcesView";
import { useParams } from "react-router-dom";

const CourseDashboardWrapper = () => {
  const { courseId } = useParams<{ courseId: string }>();
  if (!courseId) {
    return <Navigate to="/courses" replace />;
  }
  return <CourseDashboard courseId={courseId} />;
};

const App = () => (
  <BrowserRouter>
    <Toaster position="top-right" toastOptions={{ duration: 4000 }} />
    <Routes>
      <Route path="/login" element={<LoginForm />} />
      <Route path="/register" element={<RegisterForm />} />
      <Route path="/verify" element={<VerificationForm />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/sources" replace />} />
        <Route path="sources" element={<SourcesView />} />
        <Route path="chat" element={<ChatInterface />} />
        <Route path="lectures" element={<LecturePlayer />} />
        <Route path="quizzes" element={<QuizInterface />} />
        <Route path="courses" element={<CourseList />} />
        <Route path="courses/new" element={<CourseCreationForm />} />
        <Route path="courses/:courseId" element={<CourseDashboardWrapper />} />
      </Route>
    </Routes>
  </BrowserRouter>
);

export default App;
