import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { AlertCircle, Bell, FileCheck, FileText, UserCheck, Users } from 'lucide-react';
import api, { getUserRole } from '../../utils/api';

function DepartmentDashboard() {
  const { currentUser } = useAuth();
  const hasFetched = useRef(false);
  const [stats, setStats] = useState({
    pendingReviews: 0,
    totalExams: 0,
    approvedExams: 0,
    totalTeachers: 0,
    pendingUsers: 0,
    totalModules: 0,
    notifications: 0,
  });
  const [pendingExams, setPendingExams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const userRole = getUserRole(currentUser);
  const resolvedDepartmentName = String(currentUser?.department_name || '').trim();
  const departmentDisplayName = resolvedDepartmentName || 'Not Assigned';

  useEffect(() => {
    if (currentUser && !hasFetched.current) {
      hasFetched.current = true;
      fetchDashboardData();
    }
  }, [currentUser]);

  const fetchDashboardData = async () => {
    setLoading(true);
    setError(null);

    try {
      const [statsResponse, examsResponse, unreadResponse] = await Promise.all([
        api.get('/departments/dashboard'),
        api.get('/departments/exams', { params: { status: 'pending', per_page: 5 } }),
        api.get('/notifications/unread/count'),
      ]);

      if (statsResponse.data.success) {
        const dashboardStats = statsResponse.data.stats;
        const pendingReviews = Number(dashboardStats.pending_exams) || 0;
        const approvedExamsRaw = Number(dashboardStats.approved_exams);
        const approvedExams = Number.isFinite(approvedExamsRaw)
          ? approvedExamsRaw
          : Math.max(0, Number(dashboardStats.total_exams) || 0);
        const totalExams = approvedExams;

        setStats({
          pendingReviews: Math.max(0, pendingReviews),
          totalExams: Math.max(0, totalExams),
          approvedExams: Math.max(0, approvedExams),
          totalTeachers: Number(dashboardStats.total_teachers) || 0,
          pendingUsers: Number(dashboardStats.pending_users) || 0,
          totalModules: Number(dashboardStats.total_subjects) || 0,
          notifications: Number(unreadResponse?.data?.data?.unread_count) || 0,
        });
      }

      if (examsResponse.data.success) {
        setPendingExams(examsResponse.data.exams || []);
      }
    } catch (err) {
      let errorMessage = 'Failed to load dashboard data. Please try again.';

      if (err.response?.status === 403) {
        errorMessage = 'You do not have permission to access the department dashboard.';
      } else if (err.response?.status === 400) {
        errorMessage =
          err.response?.data?.message || 'Your account is not assigned to a department.';
      } else {
        errorMessage = err.response?.data?.message || errorMessage;
      }

      setError(errorMessage);
      setStats({
        pendingReviews: 0,
        totalExams: 0,
        approvedExams: 0,
        totalTeachers: 0,
        pendingUsers: 0,
        totalModules: 0,
        notifications: 0,
      });
      setPendingExams([]);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-2 border-amber-200 border-t-amber-500 mx-auto" />
          <p className="mt-4 text-sm text-muted-foreground">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  const statCardClass =
    'h-full border border-amber-200 bg-white shadow-sm transition-shadow hover:shadow-md';
  const statHeaderClass = 'flex flex-row items-center justify-between pb-2';
  const statTitleClass = 'text-sm font-semibold text-gray-800 leading-tight';

  return (
    <div className="w-full max-w-[1600px] mx-auto px-4 md:px-6 py-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-gray-900">Department Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Welcome back, {currentUser?.first_name} {currentUser?.last_name}
        </p>

        <div className="mt-3 inline-flex items-center rounded-full border border-amber-300 bg-amber-50 px-3 py-1 text-sm font-medium text-amber-900">
          Current Department: {departmentDisplayName}
        </div>

        <div className="mt-2 space-y-1 text-sm text-muted-foreground">
          <p>Role: {userRole === 'department_head' ? 'Department Head' : userRole}</p>
          <p>
            Department:{' '}
            {resolvedDepartmentName || (
              <span className="text-red-600 font-semibold">Not Assigned</span>
            )}
          </p>
          <p>
            Department ID:{' '}
            {currentUser?.department_id || (
              <span className="text-red-600 font-semibold">Not Assigned</span>
            )}
          </p>
          <p>Email: {currentUser?.email}</p>
        </div>
      </div>

      {error && (
        <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 rounded-r-md">
          <div className="flex">
            <AlertCircle className="h-5 w-5 text-yellow-500" />
            <div className="ml-3 flex-1">
              <p className="text-sm text-yellow-700">{error}</p>
              <div className="mt-4">
                <Button size="sm" onClick={fetchDashboardData}>
                  Retry
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        <Link
          to="/department/pending-approvals"
          className="block h-full rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-400"
        >
          <Card className={statCardClass}>
            <CardHeader className={statHeaderClass}>
              <CardTitle className={statTitleClass}>Exams Pending for Approval</CardTitle>
              <AlertCircle className="h-4 w-4 text-amber-700" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-amber-900">{stats.pendingReviews}</div>
            </CardContent>
          </Card>
        </Link>

        <Link
          to="/department/approved-exams"
          className="block h-full rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-400"
        >
          <Card className={statCardClass}>
            <CardHeader className={statHeaderClass}>
              <CardTitle className={statTitleClass}>Total Number of Exams</CardTitle>
              <FileCheck className="h-4 w-4 text-amber-700" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-amber-900">{stats.totalExams}</div>
            </CardContent>
          </Card>
        </Link>

        <Link
          to="/department/manage-users"
          className="block h-full rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-400"
        >
          <Card className={statCardClass}>
            <CardHeader className={statHeaderClass}>
              <CardTitle className={statTitleClass}>Total Number of Teachers</CardTitle>
              <Users className="h-4 w-4 text-amber-700" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-amber-900">{stats.totalTeachers}</div>
            </CardContent>
          </Card>
        </Link>

        <Link
          to="/department/manage-users"
          className="block h-full rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-400"
        >
          <Card className={statCardClass}>
            <CardHeader className={statHeaderClass}>
              <CardTitle className={statTitleClass}>Users Pending for Approval</CardTitle>
              <UserCheck className="h-4 w-4 text-amber-700" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-amber-900">{stats.pendingUsers}</div>
            </CardContent>
          </Card>
        </Link>

        <Link
          to="/department/modules-bank"
          className="block h-full rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-400"
        >
          <Card className={statCardClass}>
            <CardHeader className={statHeaderClass}>
              <CardTitle className={statTitleClass}>Total Number of Subjects</CardTitle>
              <FileText className="h-4 w-4 text-amber-700" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-amber-900">{stats.totalModules}</div>
            </CardContent>
          </Card>
        </Link>

        <Link
          to="/department/notifications"
          className="block h-full rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-400"
        >
          <Card className={statCardClass}>
            <CardHeader className={statHeaderClass}>
              <CardTitle className={statTitleClass}>Unread Notifications</CardTitle>
              <Bell className="h-4 w-4 text-amber-700" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-amber-900">{stats.notifications}</div>
            </CardContent>
          </Card>
        </Link>
      </div>

      <Card className="border border-amber-200 bg-white shadow-sm">
        <CardHeader>
          <CardTitle>Pending Exam Reviews</CardTitle>
          <CardDescription>{pendingExams.length} exam(s) awaiting review</CardDescription>
        </CardHeader>
        <CardContent>
          {pendingExams.length === 0 ? (
            <p className="text-center text-muted-foreground py-6">No pending exams</p>
          ) : (
            <div className="space-y-3">
              {pendingExams.map((exam) => (
                <div
                  key={exam.exam_id}
                  className="flex justify-between items-center border border-amber-200 p-3 rounded-lg"
                >
                  <div>
                    <p className="font-medium">{exam.title}</p>
                    <p className="text-sm text-muted-foreground">
                      Teacher: {exam.teacher_name || exam.teacher_id}
                    </p>
                  </div>
                  <Button size="sm" asChild>
                    <Link to={`/department/exam-review/${exam.exam_id}`}>Review</Link>
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default DepartmentDashboard;
