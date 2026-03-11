import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { FileText, Users } from 'lucide-react';
import api from '../../utils/api';

function AdminDashboard() {
  const { currentUser } = useAuth();
  const hasFetched = useRef(false);
  const [stats, setStats] = useState({
    totalExams: 0,
    totalUsers: 0,
  });
  const [recentExams, setRecentExams] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (currentUser && !hasFetched.current) {
      hasFetched.current = true;
      fetchDashboardData();
    }
  }, [currentUser]);

  const fetchDashboardData = async () => {
    try {
      const [statsRes, examsRes] = await Promise.all([
        api.get('/admin/dashboard'),
        api.get('/exams/all', {
          params: { status: 'approved', page: 1, per_page: 5 },
        }),
      ]);

      const dashboardStats = statsRes.data?.stats || {};
      setStats({
        totalExams: Number(dashboardStats.total_exams) || 0,
        totalUsers: Number(dashboardStats.total_users) || 0,
      });
      setRecentExams(examsRes.data.exams || []);
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
      setStats({ totalExams: 0, totalUsers: 0 });
      setRecentExams([]);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-amber-200 border-t-amber-500" />
      </div>
    );
  }

  const statCardClass =
    'h-full border border-amber-200 bg-white shadow-sm transition-shadow hover:shadow-md';

  return (
    <div className="w-full max-w-[1600px] mx-auto px-4 md:px-6 py-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-gray-900">Admin Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Welcome back, {currentUser?.first_name} {currentUser?.last_name}
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Card className={statCardClass}>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-semibold text-gray-800">Total Exams</CardTitle>
            <FileText className="h-4 w-4 text-amber-700" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-amber-900">{stats.totalExams}</div>
          </CardContent>
        </Card>

        <Link
          to="/admin/users"
          className="block h-full rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-400"
        >
          <Card className={statCardClass}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-semibold text-gray-800">Total Users</CardTitle>
              <Users className="h-4 w-4 text-amber-700" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-amber-900">{stats.totalUsers}</div>
              <p className="text-xs text-muted-foreground mt-1">Click to view all users</p>
            </CardContent>
          </Card>
        </Link>
      </div>

      <Card className="border border-amber-200 bg-white shadow-sm">
        <CardHeader>
          <CardTitle>Recent Exams</CardTitle>
          <CardDescription>Latest exams in the system</CardDescription>
        </CardHeader>
        <CardContent className="px-6 pb-6">
          {recentExams.length === 0 ? (
            <p className="text-sm text-muted-foreground">No exams found</p>
          ) : (
            <div className="space-y-3">
              {recentExams.map((exam) => (
                <div
                  key={exam.exam_id}
                  className="flex items-center justify-between p-3 border border-amber-200 rounded-lg"
                >
                  <div>
                    <p className="font-medium">{exam.title}</p>
                    <p className="text-sm text-muted-foreground">
                      {exam.total_questions} questions - {exam.duration_minutes} mins
                    </p>
                  </div>
                  <Button variant="outline" size="sm" asChild>
                    <Link to={`/admin/exams/${exam.exam_id}`}>View</Link>
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

export default AdminDashboard;
