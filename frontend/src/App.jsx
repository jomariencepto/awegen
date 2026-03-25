import React, { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster, toast } from 'react-hot-toast';
import { AuthProvider, useAuth } from './context/AuthContext';
import { getUserRole, getRoleDashboard } from './utils/api';
import ErrorBoundary from './components/ErrorBoundary';
import GlobalStatusPopup from './components/GlobalStatusPopup';
import { patchToastForStatusPopup } from './utils/statusPopup';

const TeacherSidebar = lazy(() => import('./components/Sidebar/TeacherSidebar'));
const DepartmentSidebar = lazy(() => import('./components/Sidebar/DepartmentSidebar'));
const AdminSidebar = lazy(() => import('./components/Sidebar/AdminSidebar'));

const Login = lazy(() => import('./pages/Auth/Login'));
const AdminManagedSignupNotice = lazy(() => import('./pages/Auth/AdminManagedSignupNotice'));
const SignupAdmin = lazy(() => import('./pages/Auth/SignupAdmin'));
const ForgotPassword = lazy(() => import('./pages/Auth/ForgotPassword'));

const TeacherDashboard = lazy(() => import('./pages/Teacher/Dashboard'));
const ManageExams = lazy(() => import('./pages/Teacher/ManageExams'));
const CreateExam = lazy(() => import('./pages/Teacher/CreateExam'));
const UploadModule = lazy(() => import('./pages/Teacher/UploadModule'));
const ReviewTOS = lazy(() => import('./pages/Teacher/ReviewTOS'));
const ReviewQuestions = lazy(() => import('./pages/Teacher/ReviewQuestions'));
const EditExam = lazy(() => import('./pages/Teacher/EditExams'));
const TeacherExamPreview = lazy(() => import('./pages/Teacher/ExamPreview'));
const TeacherModuleImages = lazy(() => import('./pages/Teacher/ModuleImages'));
const SavedExams = lazy(() => import('./pages/Teacher/SavedExams'));
const TeacherNotifications = lazy(() => import('./pages/Teacher/Notifications'));
const TeacherSettings = lazy(() => import('./pages/Teacher/Settings'));

const DepartmentDashboard = lazy(() => import('./pages/Department/Dashboard'));
const ApprovedExams = lazy(() => import('./pages/Department/ApprovedExams'));
const PendingApprovals = lazy(() => import('./pages/Department/PendingApprovals'));
const ModulesBank = lazy(() => import('./pages/Department/ModulesBank'));
const ManageUsers = lazy(() => import('./pages/Department/ManageUsers'));
const Settings = lazy(() => import('./pages/Department/Settings'));
const ExamReview = lazy(() => import('./pages/Department/ExamReview'));
const DepartmentExamPreview = lazy(() => import('./pages/Department/DepartmentExamPreview'));
const DepartmentCreateExam = lazy(() => import('./pages/Department/CreateExam'));
const DepartmentReviewQuestions = lazy(() => import('./pages/Department/ReviewQuestions'));
const UploadModuleDepartment = lazy(() => import('./pages/Department/UploadModule'));
const TOSReports = lazy(() => import('./pages/Department/TOSReports'));
const DepartmentNotifications = lazy(() => import('./pages/Department/Notifications'));
const SpecialExams = lazy(() => import('./pages/Department/SpecialExams'));
const ExamsDownload = lazy(() => import('./pages/Department/ExamsDownload'));
const DepartmentExamCompliance = lazy(() => import('./pages/Department/ExamCompliance'));

const AdminDashboard = lazy(() => import('./pages/Admin/Dashboard'));
const SystemReports = lazy(() => import('./pages/Admin/SystemReports'));
const AdminSettings = lazy(() => import('./pages/Admin/Settings'));
const DepartmentSubjects = lazy(() => import('./pages/Admin/DepartmentSubjects'));
const ExamPassword = lazy(() => import('./pages/Admin/ExamPassword'));
const UsersList = lazy(() => import('./pages/Admin/UsersList'));

const PlaceholderPage = ({ title, description }) => (
  <div className="space-y-6">
    <div>
      <h1 className="text-3xl font-bold tracking-tight text-gray-900">{title}</h1>
      <p className="mt-1 text-gray-600">{description}</p>
    </div>
    <div className="rounded-xl border border-gray-200 bg-white p-12 text-center shadow-sm">
      <div className="mb-4 text-6xl text-gray-400">🚧</div>
      <h3 className="mb-2 text-lg font-semibold text-gray-900">Coming Soon</h3>
      <p className="text-gray-500">This feature is under development.</p>
    </div>
  </div>
);

const Students = () => (
  <PlaceholderPage title="Students" description="View and manage students" />
);

const LoadingScreen = () => (
  <div className="flex min-h-screen items-center justify-center bg-gray-50">
    <div className="text-center">
      <div className="relative">
        <div className="mx-auto h-16 w-16 animate-spin rounded-full border-4 border-gray-200 border-t-yellow-500" />
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="h-8 w-8 animate-pulse rounded-full bg-yellow-500 opacity-20" />
        </div>
      </div>
      <p className="mt-6 font-medium text-gray-600">Loading AWEgen...</p>
    </div>
  </div>
);

const renderLazyElement = (Component, props = {}) => (
  <Suspense fallback={<LoadingScreen />}>
    <Component {...props} />
  </Suspense>
);

const LazyLayout = ({ Component }) => (
  <Suspense fallback={<LoadingScreen />}>
    <Component />
  </Suspense>
);

const NotFound = () => (
  <div className="flex min-h-screen items-center justify-center bg-gray-50">
    <div className="px-4 text-center">
      <div className="mb-8">
        <div className="mb-2 text-8xl font-bold text-gray-200">404</div>
        <h1 className="mb-2 text-3xl font-bold text-gray-900">Page Not Found</h1>
        <p className="mx-auto mb-8 max-w-md text-gray-600">
          The page you are looking for does not exist or has been moved.
        </p>
      </div>
      <div className="space-x-4">
        <a
          href="/auth/login"
          className="inline-block rounded-lg bg-yellow-500 px-6 py-3 font-semibold text-black shadow-sm transition-all duration-200 hover:bg-yellow-600 hover:shadow-md"
        >
          Go to Login
        </a>
        <button
          onClick={() => window.history.back()}
          className="inline-block rounded-lg border border-gray-300 bg-white px-6 py-3 font-semibold text-gray-700 transition-all duration-200 hover:bg-gray-50"
        >
          Go Back
        </button>
      </div>
    </div>
  </div>
);

function ProtectedRoute({ children, requiredRole }) {
  const { isAuthenticated, currentUser, loading } = useAuth();

  if (loading) {
    return <LoadingScreen />;
  }

  const userRole = currentUser ? getUserRole(currentUser) : 'none';

  if (import.meta.env.DEV) {
    console.log('ProtectedRoute Check:', {
      isAuthenticated,
      hasUser: Boolean(currentUser),
      userRole,
      requiredRole,
      path: window.location.pathname,
    });
  }

  if (!isAuthenticated || !currentUser) {
    if (import.meta.env.DEV) {
      console.warn('Not authenticated - redirecting to login');
    }
    return <Navigate to="/auth/login" state={{ from: window.location.pathname }} replace />;
  }

  if (requiredRole && userRole !== requiredRole) {
    if (import.meta.env.DEV) {
      console.warn(`Role mismatch: expected "${requiredRole}", got "${userRole}"`);
    }
    const dashboardPath = getRoleDashboard(userRole);
    return <Navigate to={dashboardPath} replace />;
  }

  return children;
}

function App() {
  useEffect(() => {
    const handleWheel = (event) => {
      const target = event.target;
      if (
        target instanceof HTMLElement &&
        target.tagName === 'INPUT' &&
        target.getAttribute('type') === 'number' &&
        document.activeElement === target
      ) {
        event.preventDefault();
      }
    };

    window.addEventListener('wheel', handleWheel, { passive: false });
    return () => window.removeEventListener('wheel', handleWheel);
  }, []);

  useEffect(() => {
    const unpatch = patchToastForStatusPopup(toast);
    return () => unpatch();
  }, []);

  return (
    <AuthProvider>
      <Router>
        <div className="App">
          <GlobalStatusPopup />
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
            <Route path="/" element={<Navigate to="/auth/login" replace />} />

            <Route path="/auth/login" element={renderLazyElement(Login)} />
            <Route
              path="/auth/signup"
              element={renderLazyElement(AdminManagedSignupNotice, {
                accountLabel: 'teacher',
              })}
            />
            <Route
              path="/auth/signup-department"
              element={renderLazyElement(AdminManagedSignupNotice, {
                accountLabel: 'department-head',
              })}
            />
            <Route path="/auth/signup-admin" element={renderLazyElement(SignupAdmin)} />
            <Route path="/auth/forgot-password" element={renderLazyElement(ForgotPassword)} />

            <Route
              path="/teacher"
              element={
                <ProtectedRoute requiredRole="teacher">
                  <ErrorBoundary level="route">
                    <LazyLayout Component={TeacherSidebar} />
                  </ErrorBoundary>
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard" element={renderLazyElement(TeacherDashboard)} />
              <Route path="manage-exams" element={renderLazyElement(ManageExams)} />
              <Route path="create-exam" element={renderLazyElement(CreateExam)} />
              <Route path="upload-module" element={renderLazyElement(UploadModule)} />
              <Route path="review-tos/:examId" element={renderLazyElement(ReviewTOS)} />
              <Route path="review-questions/:examId" element={renderLazyElement(ReviewQuestions)} />
              <Route path="edit-exam/:examId" element={renderLazyElement(EditExam)} />
              <Route path="exam-preview/:examId" element={renderLazyElement(TeacherExamPreview)} />
              <Route path="module-images" element={renderLazyElement(TeacherModuleImages)} />
              <Route path="saved-exams" element={renderLazyElement(SavedExams)} />
              <Route path="notifications" element={renderLazyElement(TeacherNotifications)} />
              <Route path="students" element={<Students />} />
              <Route path="settings" element={renderLazyElement(TeacherSettings)} />
            </Route>

            <Route
              path="/department"
              element={
                <ProtectedRoute requiredRole="department_head">
                  <ErrorBoundary level="route">
                    <LazyLayout Component={DepartmentSidebar} />
                  </ErrorBoundary>
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard" element={renderLazyElement(DepartmentDashboard)} />
              <Route path="create-exam" element={renderLazyElement(DepartmentCreateExam)} />
              <Route path="approved-exams" element={renderLazyElement(ApprovedExams)} />
              <Route path="pending-approvals" element={renderLazyElement(PendingApprovals)} />
              <Route path="exams-download" element={renderLazyElement(ExamsDownload)} />
              <Route path="modules-bank" element={renderLazyElement(ModulesBank)} />
              <Route path="manage-users" element={renderLazyElement(ManageUsers)} />
              <Route path="exam-compliance" element={renderLazyElement(DepartmentExamCompliance)} />
              <Route path="settings" element={renderLazyElement(Settings)} />
              <Route path="exam-review/:examId" element={renderLazyElement(ExamReview)} />
              <Route path="review-questions/:examId" element={renderLazyElement(DepartmentReviewQuestions)} />
              <Route path="exam-preview/:examId" element={renderLazyElement(DepartmentExamPreview)} />
              <Route path="upload-module" element={renderLazyElement(UploadModuleDepartment)} />
              <Route path="tos-reports" element={renderLazyElement(TOSReports)} />
              <Route path="tos-reports/:examId" element={renderLazyElement(TOSReports)} />
              <Route path="notifications" element={renderLazyElement(DepartmentNotifications)} />
            </Route>

            <Route
              path="/admin"
              element={
                <ProtectedRoute requiredRole="admin">
                  <ErrorBoundary level="route">
                    <LazyLayout Component={AdminSidebar} />
                  </ErrorBoundary>
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard" element={renderLazyElement(AdminDashboard)} />
              <Route path="users" element={renderLazyElement(UsersList)} />
              <Route path="settings" element={renderLazyElement(AdminSettings)} />
              <Route path="exam-password" element={renderLazyElement(ExamPassword)} />
              <Route path="departments-subjects" element={renderLazyElement(DepartmentSubjects)} />
              <Route path="special-exams" element={renderLazyElement(SpecialExams)} />
              <Route path="system-reports" element={renderLazyElement(SystemReports)} />
              <Route path="exams/:examId" element={renderLazyElement(TeacherExamPreview)} />
            </Route>

            <Route path="*" element={<NotFound />} />
          </Routes>
        </div>
      </Router>
    </AuthProvider>
  );
}

export default App;
