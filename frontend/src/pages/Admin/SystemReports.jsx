import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import {
  CheckCircle2,
  Clock3,
  Download,
  FileText,
  Loader2,
  TrendingUp,
  Users,
} from 'lucide-react';
import api from '../../utils/api';

function SystemReports() {
  const [reportType] = useState('overview');
  const [dateRange] = useState('month');
  const [stats, setStats] = useState({
    totalUsers: 0,
    totalExams: 0,
    approvedExams: 0,
    pendingExams: 0,
    totalModules: 0,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isExporting, setIsExporting] = useState(null);

  useEffect(() => {
    fetchReportData();
  }, [reportType, dateRange]);

  const fetchReportData = async () => {
    setIsLoading(true);
    try {
      const response = await api.get('/reports/system', {
        params: { type: reportType, range: dateRange },
      });
      setStats(
        response.data.stats || {
          totalUsers: 0,
          totalExams: 0,
          approvedExams: 0,
          pendingExams: 0,
          totalModules: 0,
        }
      );
    } catch (error) {
      console.error('Error fetching report data:', error);
      setStats({
        totalUsers: 0,
        totalExams: 0,
        approvedExams: 0,
        pendingExams: 0,
        totalModules: 0,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleExportReport = async (format) => {
    setIsExporting(format);
    try {
      const response = await api.get(`/reports/export/${format}`, {
        params: { type: reportType, range: dateRange },
        responseType: 'blob',
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `system-report-${Date.now()}.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error exporting report:', error);
      alert('Failed to export report. Please try again.');
    } finally {
      setIsExporting(null);
    }
  };

  const approvalRate =
    stats.totalExams > 0 ? Math.round((stats.approvedExams / stats.totalExams) * 100) : 0;

  const statCards = [
    {
      title: 'Total Users',
      value: stats.totalUsers,
      subtext: 'Active system users',
      icon: Users,
    },
    {
      title: 'Total Exams',
      value: stats.totalExams,
      subtext: 'Created exams',
      icon: FileText,
    },
    {
      title: 'Approved Exams',
      value: stats.approvedExams,
      subtext: 'Approved for use',
      icon: CheckCircle2,
    },
    {
      title: 'Pending Exams',
      value: stats.pendingExams,
      subtext: 'Awaiting approval',
      icon: Clock3,
    },
    {
      title: 'Total Modules',
      value: stats.totalModules,
      subtext: 'Learning modules',
      icon: FileText,
    },
  ];

  const StatCard = ({ title, value, subtext, icon: Icon }) => (
    <Card className="h-full border border-amber-200 bg-white shadow-sm transition-shadow hover:shadow-md">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-semibold text-gray-800">{title}</CardTitle>
        <div className="rounded-lg bg-amber-100 p-2">
          <Icon className="h-4 w-4 text-amber-700" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-bold text-amber-900">{value}</div>
        <p className="text-xs text-muted-foreground mt-1">{subtext}</p>
      </CardContent>
    </Card>
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <Loader2 className="animate-spin h-10 w-10 text-amber-600 mx-auto" />
          <p className="mt-3 text-sm text-muted-foreground">Loading system reports...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-[1600px] mx-auto px-4 md:px-6 py-6 space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">System Reports</h1>
          <p className="text-sm text-muted-foreground mt-1">
            View and export analytics for users, exams, approvals, and modules.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            className="border-amber-300 text-amber-900 hover:bg-amber-50"
            onClick={() => handleExportReport('pdf')}
            disabled={isExporting === 'pdf'}
          >
            {isExporting === 'pdf' ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Download className="h-4 w-4 mr-2" />
            )}
            Export PDF
          </Button>
          <Button
            variant="outline"
            className="border-amber-300 text-amber-900 hover:bg-amber-50"
            onClick={() => handleExportReport('csv')}
            disabled={isExporting === 'csv'}
          >
            {isExporting === 'csv' ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Download className="h-4 w-4 mr-2" />
            )}
            Export CSV
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {statCards.map((item) => (
          <StatCard
            key={item.title}
            title={item.title}
            value={item.value}
            subtext={item.subtext}
            icon={item.icon}
          />
        ))}
      </div>

      <Card className="border border-amber-200 bg-white shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-gray-900">
            <TrendingUp className="h-5 w-5 text-amber-700" />
            Approval Performance
          </CardTitle>
          <CardDescription>
            Percentage of approved exams based on all created exams.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-end justify-between gap-4">
            <div className="text-4xl font-bold text-amber-900">{approvalRate}%</div>
            <p className="text-sm text-muted-foreground">
              {stats.approvedExams} approved out of {stats.totalExams}
            </p>
          </div>
          <div className="h-2.5 w-full rounded-full bg-amber-100">
            <div
              className="h-2.5 rounded-full bg-amber-500 transition-all"
              style={{ width: `${Math.min(Math.max(approvalRate, 0), 100)}%` }}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default SystemReports;
