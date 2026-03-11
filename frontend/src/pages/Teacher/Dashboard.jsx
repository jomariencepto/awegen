import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import {
  Activity,
  AlertCircle,
  Bell,
  BookOpen,
  CheckCircle,
  Clock,
  Eye,
  FileEdit,
  FileText,
  Plus,
  TrendingUp,
} from 'lucide-react';
import api from '../../utils/api';
import { fetchAllTeacherExams, sortExamsNewestFirst } from '../../utils/exams';

function TeacherDashboard() {
  const { currentUser } = useAuth();
  const [stats, setStats] = useState({
    totalExams: 0,
    totalModules: 0,
    pendingActions: 0,
    notifications: 0,
  });
  const [recentExams, setRecentExams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (currentUser) {
      fetchDashboardData();
    }
  }, [currentUser]);

  const fetchDashboardData = async () => {
    if (!currentUser?.user_id) {
      setError('User information not available');
      setLoading(false);
      return;
    }

    try {
      const results = await Promise.allSettled([
        fetchAllTeacherExams(currentUser.user_id),
        api.get(`/modules/teacher/${currentUser.user_id}`),
        api.get('/notifications/unread/count'),
      ]);

      const nextStats = {
        totalExams: 0,
        totalModules: 0,
        pendingActions: 0,
        notifications: 0,
      };
      let revisionRequiredCount = 0;
      let unreadCount = 0;

      if (results[0].status === 'fulfilled') {
        const exams = sortExamsNewestFirst(results[0].value || []);
        const pendingCount = exams.filter((exam) => {
          const status = String(exam.admin_status || '').toLowerCase();
          return status === 'pending' || status === 'revision_required';
        }).length;
        revisionRequiredCount = exams.filter(
          (exam) => String(exam.admin_status || '').toLowerCase() === 'revision_required'
        ).length;
        nextStats.totalExams = exams.length;
        nextStats.pendingActions = pendingCount;
        setRecentExams(exams.slice(0, 5));
      }

      if (results[1].status === 'fulfilled') {
        const modulesData = results[1].value.data;
        nextStats.totalModules = modulesData.total || 0;
      }

      if (results[2].status === 'fulfilled') {
        const notificationsData = results[2].value.data;
        unreadCount = Number(notificationsData?.data?.unread_count) || 0;
      }
      // Keep revision-required visible in dashboard notifications even if unread feed is empty.
      nextStats.notifications = Math.max(unreadCount, revisionRequiredCount);
      setStats(nextStats);
    } catch (fetchError) {
      console.error('Error fetching dashboard data:', fetchError);
      setError('Failed to load dashboard data.');
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    const statusMap = {
      approved: { label: 'Approved', className: 'bg-amber-100 text-amber-900 border-amber-300' },
      pending: { label: 'Pending', className: 'bg-amber-50 text-amber-800 border-amber-300' },
      draft: { label: 'Draft', className: 'bg-amber-50 text-amber-700 border-amber-200' },
      rejected: { label: 'Rejected', className: 'bg-red-50 text-red-700 border-red-200' },
      revision_required: {
        label: 'Revision',
        className: 'bg-amber-100 text-amber-900 border-amber-300',
      },
      'Re-Used': { label: 'Revised', className: 'bg-emerald-50 text-emerald-700 border-emerald-300' },
    };

    const config = statusMap[status] || statusMap.draft;
    return <Badge className={config.className}>{config.label}</Badge>;
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'approved':
        return <CheckCircle className="h-4 w-4 text-amber-700" />;
      case 'pending':
        return <Clock className="h-4 w-4 text-amber-600" />;
      case 'draft':
        return <FileEdit className="h-4 w-4 text-amber-500" />;
      default:
        return <AlertCircle className="h-4 w-4 text-amber-500" />;
    }
  };

  const getDisplayName = () => {
    if (!currentUser) return 'Teacher';
    if (currentUser.first_name && currentUser.last_name) {
      return `${currentUser.first_name} ${currentUser.last_name}`;
    }
    return currentUser.name || currentUser.username || 'Teacher';
  };

  const statCardClass =
    'h-full min-h-[132px] border border-amber-200 bg-white shadow-sm transition-shadow hover:shadow-md';
  const statIconWrapClass = 'flex-shrink-0 rounded-lg bg-amber-100 p-3.5';
  const statContentClass = 'h-full';
  const statContentStyle = { padding: '2.4rem 1.5rem 1.5rem' };
  const statRowClass = 'flex items-start justify-between gap-4 h-full';
  const statTextBlockClass = 'flex-1 min-w-0 pt-1 space-y-2.5';
  const statLabelClass = 'text-[11px] font-semibold text-amber-800 uppercase tracking-wide leading-5';
  const statValueClass = 'text-4xl font-bold text-amber-900 leading-none';
  const statMetaClass = 'flex items-center gap-1.5 text-xs leading-relaxed';

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-amber-200 border-t-amber-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] space-y-4">
        <AlertCircle className="h-12 w-12 text-red-500" />
        <p className="text-red-600 text-center">{error}</p>
        <Button onClick={fetchDashboardData}>Retry</Button>
      </div>
    );
  }

  return (
    <div className="w-full max-w-[1600px] mx-auto px-4 md:px-6 py-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900 mb-1">Teacher Dashboard</h1>
          <p className="text-sm text-muted-foreground flex items-center gap-2">
            <Activity className="h-4 w-4 text-amber-700" />
            Welcome back, <span className="font-medium text-gray-900">{getDisplayName()}</span>
          </p>
        </div>
        <Link to="/teacher/create-exam">
          <Button className="bg-amber-500 text-amber-950 hover:bg-amber-600 border border-amber-300 shadow-sm">
            <Plus className="mr-2 h-4 w-4" />
            Create Exam
          </Button>
        </Link>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <Link
          to="/teacher/manage-exams"
          className="block h-full rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-400"
        >
          <Card className={statCardClass}>
            <CardContent className={statContentClass} style={statContentStyle}>
              <div className={statRowClass}>
                <div className={statTextBlockClass}>
                  <p className={statLabelClass}>
                    Total Exams
                  </p>
                  <p className={statValueClass}>{stats.totalExams}</p>
                  <div className={statMetaClass}>
                    {stats.pendingActions > 0 ? (
                      <>
                        <Clock className="h-3 w-3 text-amber-600" />
                        <span className="text-amber-800 font-medium">
                          {stats.pendingActions} need action
                        </span>
                      </>
                    ) : (
                      <>
                        <CheckCircle className="h-3 w-3 text-amber-700" />
                        <span className="text-amber-800 font-medium">All approved</span>
                      </>
                    )}
                  </div>
                </div>
                <div className={statIconWrapClass}>
                  <FileText className="h-6 w-6 text-amber-700" />
                </div>
              </div>
            </CardContent>
          </Card>
        </Link>

        <Link
          to="/teacher/upload-module"
          className="block h-full rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-400"
        >
          <Card className={statCardClass}>
            <CardContent className={statContentClass} style={statContentStyle}>
              <div className={statRowClass}>
                <div className={statTextBlockClass}>
                  <p className={statLabelClass}>
                    Total Modules
                  </p>
                  <p className={statValueClass}>{stats.totalModules}</p>
                  <div className={statMetaClass}>
                    <TrendingUp className="h-3 w-3 text-amber-700" />
                    <span className="text-amber-800 font-medium">Active resources</span>
                  </div>
                </div>
                <div className={statIconWrapClass}>
                  <BookOpen className="h-6 w-6 text-amber-700" />
                </div>
              </div>
            </CardContent>
          </Card>
        </Link>

        <Link
          to="/teacher/manage-exams"
          className="block h-full rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-400"
        >
          <Card className={statCardClass}>
            <CardContent className={statContentClass} style={statContentStyle}>
              <div className={statRowClass}>
                <div className={statTextBlockClass}>
                  <p className={statLabelClass}>
                    Pending Actions
                  </p>
                  <p className={statValueClass}>{stats.pendingActions}</p>
                  <div className={statMetaClass}>
                    <AlertCircle className="h-3 w-3 text-amber-700" />
                    <span className="text-amber-800 font-medium">
                      {stats.pendingActions > 0 ? 'Requires attention' : 'No actions needed'}
                    </span>
                  </div>
                </div>
                <div className={statIconWrapClass}>
                  <AlertCircle className="h-6 w-6 text-amber-700" />
                </div>
              </div>
            </CardContent>
          </Card>
        </Link>

        <Link
          to="/teacher/notifications"
          className="block h-full rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-400"
        >
          <Card className={statCardClass}>
            <CardContent className={statContentClass} style={statContentStyle}>
              <div className={statRowClass}>
                <div className={statTextBlockClass}>
                  <p className={statLabelClass}>
                    Notifications
                  </p>
                  <p className={statValueClass}>{stats.notifications}</p>
                  <div className={statMetaClass}>
                    <Bell className="h-3 w-3 text-amber-700" />
                    <span className="text-amber-800 font-medium">
                      {stats.notifications > 0 ? 'New alerts' : 'All caught up'}
                    </span>
                  </div>
                </div>
                <div className={`${statIconWrapClass} relative`}>
                  <Bell className="h-6 w-6 text-amber-700" />
                  {stats.notifications > 0 && (
                    <span className="absolute -right-1 -top-1 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white">
                      {stats.notifications}
                    </span>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </Link>
      </div>

      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-gray-900">Recent Exams</h2>
          <Link
            to="/teacher/manage-exams"
            className="text-amber-700 hover:text-amber-800 text-sm font-medium transition-colors"
          >
            View All &rarr;
          </Link>
        </div>

        <Card className="border border-amber-200 bg-white shadow-sm transition-shadow hover:shadow-md">
          <CardContent className="p-0">
            {recentExams.length === 0 ? (
              <div className="text-center px-4 py-12">
                <FileText className="h-12 w-12 mx-auto text-amber-300 mb-3" />
                <p className="font-medium text-gray-900 mb-1">No recent exams found</p>
                <p className="text-sm text-gray-500">Create your first exam to get started</p>
                <Link to="/teacher/create-exam" className="mt-4 inline-block">
                  <Button className="bg-amber-500 text-amber-950 hover:bg-amber-600 border border-amber-300">
                    <Plus className="mr-2 h-4 w-4" />
                    Create Exam
                  </Button>
                </Link>
              </div>
            ) : (
              <div>
                {recentExams.map((exam, index) => (
                  <div
                    key={exam.exam_id}
                    className={`group p-4 flex items-center justify-between gap-4 transition-colors hover:bg-amber-50 ${
                      index < recentExams.length - 1 ? 'border-b border-amber-100' : ''
                    }`}
                  >
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <div className="flex-shrink-0">{getStatusIcon(exam.admin_status)}</div>
                      <div className="min-w-0 flex-1">
                        <h3 className="text-sm font-semibold text-gray-900 truncate">{exam.title}</h3>
                        <p className="text-xs text-gray-500 mt-0.5">
                          {exam.subject_name} - {exam.total_questions} Questions
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 flex-shrink-0">
                      {getStatusBadge(exam.admin_status)}
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 hover:text-amber-700 hover:bg-amber-50"
                          asChild
                        >
                          <Link to={`/teacher/exam-preview/${exam.exam_id}`} title="Preview">
                            <Eye className="h-4 w-4" />
                          </Link>
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 hover:text-amber-700 hover:bg-amber-50"
                          asChild
                        >
                          <Link to={`/teacher/edit-exam/${exam.exam_id}`} title="Edit">
                            <FileEdit className="h-4 w-4" />
                          </Link>
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default TeacherDashboard;
