// src/App.jsx - OPTIMIZED VERSION
import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster, toast } from 'react-hot-toast';
import { AuthProvider, useAuth } from './context/AuthContext';
import { getUserRole, getRoleDashboard } from './utils/api';
import ErrorBoundary from './components/ErrorBoundary';
import GlobalStatusPopup from './components/GlobalStatusPopup';
import { patchToastForStatusPopup } from './utils/statusPopup';

// Layout Components
import TeacherSidebar from './components/Sidebar/TeacherSidebar';
import DepartmentSidebar from './components/Sidebar/DepartmentSidebar';
import AdminSidebar from './components/Sidebar/AdminSidebar';

// Auth Pages
import Login from './pages/Auth/Login';
import SignupTeacher from './pages/Auth/SignupTeacher';
import SignupDepartment from './pages/Auth/SignupDepartment';
import SignupAdmin from './pages/Auth/SignupAdmin';
import ForgotPassword from './pages/Auth/ForgotPassword';

// Teacher Pages
import TeacherDashboard from './pages/Teacher/Dashboard';
import ManageExams from './pages/Teacher/ManageExams';
import CreateExam from './pages/Teacher/CreateExam';
import UploadModule from './pages/Teacher/UploadModule';
import ReviewTOS from './pages/Teacher/ReviewTOS';
import ReviewQuestions from './pages/Teacher/ReviewQuestions';
import EditExam from './pages/Teacher/EditExams';
import TeacherExamPreview from './pages/Teacher/ExamPreview';
import TeacherModuleImages from './pages/Teacher/ModuleImages';
import SavedExams from './pages/Teacher/SavedExams';
import TeacherNotifications from './pages/Teacher/Notifications';
import TeacherSettings from './pages/Teacher/Settings';

// Department Pages
import DepartmentDashboard from './pages/Department/Dashboard';
import ApprovedExams from './pages/Department/ApprovedExams';
import PendingApprovals from './pages/Department/PendingApprovals';
import ModulesBank from './pages/Department/ModulesBank';  // ✅ NEW
import ManageUsers from './pages/Department/ManageUsers';
import Settings from './pages/Department/Settings';
import ExamReview from './pages/Department/ExamReview';
import DepartmentExamPreview from './pages/Department/DepartmentExamPreview';
import DepartmentCreateExam from './pages/Department/CreateExam';
import UploadModuleDepartment from './pages/Department/UploadModule';
import TOSReports from './pages/Department/TOSReports';
import DepartmentNotifications from './pages/Department/Notifications';

// Admin Pages
import AdminDashboard from './pages/Admin/Dashboard';
import SpecialExams from './pages/Department/SpecialExams';
import ExamsDownload from './pages/Department/ExamsDownload';
import SystemReports from './pages/Admin/SystemReports';
import AdminSettings from './pages/Admin/Settings';
import DepartmentSubjects from './pages/Admin/DepartmentSubjects';
import ExamPassword from './pages/Admin/ExamPassword';
import UsersList from './pages/Admin/UsersList';

// Placeholder components for missing pages
const PlaceholderPage = ({ title, description }) => (
  <div className="space-y-6">
    <div>
      <h1 className="text-3xl font-bold tracking-tight text-gray-900">{title}</h1>
      <p className="text-gray-600 mt-1">{description}</p>
    </div>
    <div className="bg-white rounded-xl border border-gray-200 p-12 text-center shadow-sm">
      <div className="text-gray-400 text-6xl mb-4">🚧</div>
      <h3 className="text-lg font-semibold text-gray-900 mb-2">Coming Soon</h3>
      <p className="text-gray-500">This feature is under development.</p>
    </div>
  </div>
);

const Students = () => <PlaceholderPage title="Students" description="View and manage students" />;

// Enhanced Loading Component
const LoadingScreen = () => (
  <div className="flex items-center justify-center min-h-screen bg-gray-50">
    <div className="text-center">
      <div className="relative">
        <div className="animate-spin rounded-full h-16 w-16 border-4 border-gray-200 border-t-yellow-500 mx-auto"></div>
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-8 h-8 bg-yellow-500 rounded-full opacity-20 animate-pulse"></div>
        </div>
      </div>
      <p className="mt-6 text-gray-600 font-medium">Loading AWEgen...</p>
    </div>
  </div>
);

// Enhanced 404 Component
const NotFound = () => (
  <div className="flex items-center justify-center min-h-screen bg-gray-50">
    <div className="text-center px-4">
      <div className="mb-8">
        <div className="text-8xl font-bold text-gray-200 mb-2">404</div>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Page Not Found</h1>
        <p className="text-gray-600 mb-8 max-w-md mx-auto">
          The page you're looking for doesn't exist or has been moved.
        </p>
      </div>
      <div className="space-x-4">
        <a
          href="/auth/login"
          className="inline-block px-6 py-3 bg-yellow-500 hover:bg-yellow-600 text-black font-semibold rounded-lg transition-all duration-200 shadow-sm hover:shadow-md"
        >
          Go to Login
        </a>
        <button
          onClick={() => window.history.back()}
          className="inline-block px-6 py-3 bg-white hover:bg-gray-50 text-gray-700 font-semibold rounded-lg border border-gray-300 transition-all duration-200"
        >
          Go Back
        </button>
      </div>
    </div>
  </div>
);

// Protected Route Component with Enhanced Security
function ProtectedRoute({ children, requiredRole }) {
  const { isAuthenticated, currentUser, loading } = useAuth();

  // Show loading screen while checking authentication
  if (loading) {
    return <LoadingScreen />;
  }

  // Get properly mapped role
  const userRole = currentUser ? getUserRole(currentUser) : 'none';

  // Debug logging (only in development)
  if (import.meta.env.DEV) {
    console.log('🔒 ProtectedRoute Check:', {
      isAuthenticated,
      hasUser: !!currentUser,
      userRole,
      requiredRole,
      path: window.location.pathname,
    });
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated || !currentUser) {
    if (import.meta.env.DEV) {
      console.warn('❌ Not authenticated - redirecting to login');
    }
    return <Navigate to="/auth/login" state={{ from: window.location.pathname }} replace />;
  }

  // Check role-based access
  if (requiredRole && userRole !== requiredRole) {
    if (import.meta.env.DEV) {
      console.warn(`❌ Role mismatch: expected "${requiredRole}", got "${userRole}"`);
    }
    const dashboardPath = getRoleDashboard(userRole);
    return <Navigate to={dashboardPath} replace />;
  }

  // Render protected content
  return children;
}

function App() {
  // Prevent mouse-wheel from incrementing/decrementing focused number inputs
  useEffect(() => {
    const handleWheel = (e) => {
      const target = e.target;
      if (
        target instanceof HTMLElement &&
        target.tagName === 'INPUT' &&
        target.getAttribute('type') === 'number' &&
        document.activeElement === target
      ) {
        e.preventDefault();
      }
    };

    window.addEventListener('wheel', handleWheel, { passive: false });
    return () => window.removeEventListener('wheel', handleWheel);
  }, []);

  // Show full-page status popups for all toast success/error calls.
  useEffect(() => {
    const unpatch = patchToastForStatusPopup(toast);
    return () => unpatch();
  }, []);

  return (
    <AuthProvider>
      <Router>
        <div className="App">
          <GlobalStatusPopup />
          {/* Toast Notifications */}
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 4000,
              style: {
                background: '#fff',
                color: '#333',
                padding: '16px',
                borderRadius: '8px',
                boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
                fontSize: '14px',
              },
              success: {
                duration: 3000,
                iconTheme: {
                  primary: '#10B981',
                  secondary: '#fff',
                },
                style: {
                  background: '#F0FDF4',
                  color: '#166534',
                  border: '1px solid #86EFAC',
                },
              },
              error: {
                duration: 4000,
                iconTheme: {
                  primary: '#EF4444',
                  secondary: '#fff',
                },
                style: {
                  background: '#FEF2F2',
                  color: '#991B1B',
                  border: '1px solid #FCA5A5',
                },
              },
              loading: {
                iconTheme: {
                  primary: '#EAB308',
                  secondary: '#fff',
                },
              },
            }}
          />

          <Routes>
            {/* Root Redirect */}
            <Route path="/" element={<Navigate to="/auth/login" replace />} />

            {/* Auth Routes */}
            <Route path="/auth/login" element={<Login />} />
            <Route path="/auth/signup" element={<SignupTeacher />} />
            <Route path="/auth/signup-department" element={<SignupDepartment />} />
            <Route path="/auth/signup-admin" element={<SignupAdmin />} />
            <Route path="/auth/forgot-password" element={<ForgotPassword />} />

            {/* Teacher Routes */}
            <Route
              path="/teacher"
              element={
                <ProtectedRoute requiredRole="teacher">
                  <ErrorBoundary level="route">
                    <TeacherSidebar />
                  </ErrorBoundary>
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard" element={<TeacherDashboard />} />
              <Route path="manage-exams" element={<ManageExams />} />
              <Route path="create-exam" element={<CreateExam />} />
              <Route path="upload-module" element={<UploadModule />} />
              <Route path="review-tos/:examId" element={<ReviewTOS />} />
              <Route path="review-questions/:examId" element={<ReviewQuestions />} />
              <Route path="edit-exam/:examId" element={<EditExam />} />
              <Route path="exam-preview/:examId" element={<TeacherExamPreview />} />
              <Route path="module-images" element={<TeacherModuleImages />} />
              <Route path="saved-exams" element={<SavedExams />} />
              <Route path="notifications" element={<TeacherNotifications />} />
              <Route path="students" element={<Students />} />
              <Route path="settings" element={<TeacherSettings />} />
            </Route>

            {/* Department Routes */}
            <Route
              path="/department"
              element={
                <ProtectedRoute requiredRole="department_head">
                  <ErrorBoundary level="route">
                    <DepartmentSidebar />
                  </ErrorBoundary>
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard" element={<DepartmentDashboard />} />
              <Route path="create-exam" element={<DepartmentCreateExam />} />
              <Route path="approved-exams" element={<ApprovedExams />} />
              <Route path="pending-approvals" element={<PendingApprovals />} />
              <Route path="exams-download" element={<ExamsDownload />} />
              <Route path="modules-bank" element={<ModulesBank />} /> {/* ✅ NEW */}
              <Route path="manage-users" element={<ManageUsers />} />
              <Route path="settings" element={<Settings />} />
              <Route path="exam-review/:examId" element={<ExamReview />} />
              <Route path="exam-preview/:examId" element={<DepartmentExamPreview />} />
              <Route path="upload-module" element={<UploadModuleDepartment />} />
              <Route path="tos-reports" element={<TOSReports />} />
              <Route path="tos-reports/:examId" element={<TOSReports />} />
              <Route path="notifications" element={<DepartmentNotifications />} />
            </Route>

            {/* Admin Routes */}
            <Route
              path="/admin"
              element={
                <ProtectedRoute requiredRole="admin">
                  <ErrorBoundary level="route">
                    <AdminSidebar />
                  </ErrorBoundary>
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard" element={<AdminDashboard />} />
              <Route path="users" element={<UsersList />} />
              <Route path="settings" element={<AdminSettings />} />
              <Route path="exam-password" element={<ExamPassword />} />
              <Route path="departments-subjects" element={<DepartmentSubjects />} />
              <Route path="special-exams" element={<SpecialExams />} />
              <Route path="system-reports" element={<SystemReports />} />
              <Route path="exams/:examId" element={<TeacherExamPreview />} />
            </Route>

            {/* 404 Not Found */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </div>
      </Router>
    </AuthProvider>
  );
}

export default App;
