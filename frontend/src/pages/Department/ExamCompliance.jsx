import React, { useEffect, useMemo, useState } from 'react';
import toast from 'react-hot-toast';
import {
  BellRing,
  CheckCircle2,
  Clock3,
  RefreshCw,
  Search,
  Users,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import api from '../../utils/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';

const getTeacherStatusVariant = (status) => {
  switch (status) {
    case 'completed':
      return 'success';
    case 'in_progress':
      return 'warning';
    case 'missing':
      return 'destructive';
    default:
      return 'secondary';
  }
};

function DepartmentExamCompliance() {
  const { currentUser } = useAuth();
  const [categories, setCategories] = useState([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [loadingCategories, setLoadingCategories] = useState(true);
  const [loadingData, setLoadingData] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [sendingReminderKey, setSendingReminderKey] = useState(null);
  const [complianceData, setComplianceData] = useState({
    department_name: '',
    category: null,
    summary: null,
    teachers: [],
  });

  const resolvedDepartmentName = String(
    currentUser?.department_name || complianceData.department_name || ''
  ).trim();

  useEffect(() => {
    let cancelled = false;

    const fetchCategories = async () => {
      setLoadingCategories(true);
      try {
        const response = await api.get('/exams/categories');
        const fetchedCategories = response.data?.categories || [];

        if (cancelled) {
          return;
        }

        setCategories(fetchedCategories);

        if (fetchedCategories.length > 0) {
          const preferredCategory =
            fetchedCategories.find((category) =>
              String(category.category_name || '').toLowerCase().includes('midterm')
            ) ||
            fetchedCategories.find((category) =>
              String(category.category_name || '').toLowerCase().includes('final')
            ) ||
            fetchedCategories[0];

          setSelectedCategoryId(String(preferredCategory.category_id));
        }
      } catch (error) {
        console.error('Error fetching exam categories:', error);
        toast.error(error.response?.data?.message || 'Failed to load exam terms');
      } finally {
        if (!cancelled) {
          setLoadingCategories(false);
        }
      }
    };

    fetchCategories();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedCategoryId) {
      return;
    }

    fetchCompliance(selectedCategoryId);
  }, [selectedCategoryId]);

  const fetchCompliance = async (categoryId, options = {}) => {
    const isManualRefresh = Boolean(options.manual);

    if (isManualRefresh) {
      setRefreshing(true);
    } else {
      setLoadingData(true);
    }

    try {
      const response = await api.get('/departments/exam-compliance', {
        params: { category_id: Number(categoryId) },
      });

      setComplianceData({
        department_name: response.data?.department_name || '',
        category: response.data?.category || null,
        summary: response.data?.summary || null,
        teachers: response.data?.teachers || [],
      });
    } catch (error) {
      console.error('Error fetching department exam compliance:', error);
      toast.error(error.response?.data?.message || 'Failed to load exam follow-up data');
      setComplianceData({
        department_name: '',
        category: null,
        summary: null,
        teachers: [],
      });
    } finally {
      if (isManualRefresh) {
        setRefreshing(false);
      } else {
        setLoadingData(false);
      }
    }
  };

  const filteredTeachers = useMemo(() => {
    const normalizedTerm = searchTerm.trim().toLowerCase();

    if (!normalizedTerm) {
      return complianceData.teachers || [];
    }

    return (complianceData.teachers || []).filter((teacher) => {
      const fullName = `${teacher.first_name || ''} ${teacher.last_name || ''}`.trim().toLowerCase();
      const email = String(teacher.email || '').toLowerCase();
      const teacherStatus = String(teacher.teacher_status_label || '').toLowerCase();
      const examTitle = String(teacher.exam_title || '').toLowerCase();
      const examStatus = String(teacher.exam_status_label || '').toLowerCase();

      return (
        fullName.includes(normalizedTerm) ||
        email.includes(normalizedTerm) ||
        teacherStatus.includes(normalizedTerm) ||
        examTitle.includes(normalizedTerm) ||
        examStatus.includes(normalizedTerm)
      );
    });
  }, [complianceData.teachers, searchTerm]);

  const summaryCards = useMemo(() => {
    const summary = complianceData.summary || {};

    return [
      {
        key: 'expected_teachers',
        label: 'Expected Teachers',
        value: Number(summary.expected_teachers) || 0,
        icon: Users,
      },
      {
        key: 'completed_teachers',
        label: 'Completed',
        value: Number(summary.completed_teachers) || 0,
        icon: CheckCircle2,
      },
      {
        key: 'in_progress_teachers',
        label: 'In Progress',
        value: Number(summary.in_progress_teachers) || 0,
        icon: Clock3,
      },
      {
        key: 'teachers_needing_follow_up',
        label: 'Need Follow-Up',
        value: Number(summary.teachers_needing_follow_up) || 0,
        icon: BellRing,
      },
      {
        key: 'incomplete_exams',
        label: 'Incomplete Exams',
        value: Number(summary.incomplete_exams) || 0,
        icon: RefreshCw,
      },
    ];
  }, [complianceData.summary]);

  const sendReminder = async (teacherIds = [], reminderKey = 'all') => {
    if (!selectedCategoryId) {
      toast.error('Select a term first');
      return;
    }

    setSendingReminderKey(reminderKey);
    try {
      const response = await api.post('/departments/exam-compliance/remind', {
        category_id: Number(selectedCategoryId),
        teacher_ids: teacherIds,
      });

      const notifiedCount = Number(response.data?.notified_count) || 0;
      const emailedCount = Number(response.data?.emailed_count) || 0;
      const baseMessage = response.data?.message || 'Follow-up reminders sent';

      toast.success(
        emailedCount > 0
          ? `${baseMessage} ${emailedCount} email(s) were sent too.`
          : baseMessage
      );
    } catch (error) {
      console.error('Error sending follow-up reminders:', error);
      toast.error(error.response?.data?.message || 'Failed to send follow-up reminders');
    } finally {
      setSendingReminderKey(null);
    }
  };

  if (loadingCategories) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="text-center">
          <div className="mx-auto h-12 w-12 animate-spin rounded-full border-2 border-amber-200 border-t-amber-500" />
          <p className="mt-4 text-sm text-muted-foreground">Loading exam terms...</p>
        </div>
      </div>
    );
  }

  if (!categories.length) {
    return (
      <Card className="border border-amber-200 bg-white shadow-sm">
        <CardHeader>
          <CardTitle>Exam Follow-Up</CardTitle>
          <CardDescription>No exam categories are configured yet.</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Add exam categories first so the department can track expected exams per term.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="w-full max-w-[1600px] mx-auto px-4 md:px-6 py-6 space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">Exam Follow-Up</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Track which teachers in {resolvedDepartmentName || 'your department'} still need to
            create or submit one exam for the selected term.
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Each teacher is expected to have one exam for the selected term, such as Midterm or Final.
          </p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="min-w-[220px]">
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-amber-900">
              Term / Category
            </label>
            <select
              value={selectedCategoryId}
              onChange={(event) => setSelectedCategoryId(event.target.value)}
              className="flex h-10 w-full rounded-md border border-amber-200 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-200"
            >
              {categories.map((category) => (
                <option key={category.category_id} value={category.category_id}>
                  {category.category_name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => fetchCompliance(selectedCategoryId, { manual: true })}
              disabled={refreshing || loadingData || !selectedCategoryId}
              className="border-amber-300 text-amber-800 hover:bg-amber-100"
            >
              <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Button
              type="button"
              onClick={() => sendReminder([], 'all')}
              disabled={
                loadingData ||
                !selectedCategoryId ||
                sendingReminderKey === 'all' ||
                !(Number(complianceData.summary?.teachers_needing_follow_up) > 0)
              }
            >
              <BellRing className="mr-2 h-4 w-4" />
              {sendingReminderKey === 'all' ? 'Sending...' : 'Remind All Incomplete'}
            </Button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
        {summaryCards.map((card) => {
          const Icon = card.icon;
          return (
            <Card key={card.key} className="border border-amber-200 bg-white shadow-sm">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-semibold text-gray-800">{card.label}</CardTitle>
                <Icon className="h-4 w-4 text-amber-700" />
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-amber-900">{card.value}</div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card className="border border-amber-200 bg-white shadow-sm">
        <CardHeader className="gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <CardTitle>Teacher Exam Compliance</CardTitle>
            <CardDescription>
              {complianceData.category?.category_name || 'Selected term'} requires one exam per teacher
            </CardDescription>
          </div>

          <div className="w-full max-w-md">
            <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-amber-900">
              Search teachers or exams
            </label>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <Input
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
                placeholder="Search by name, email, or exam..."
                className="pl-9"
              />
            </div>
          </div>
        </CardHeader>

        <CardContent>
          {loadingData ? (
            <div className="flex items-center justify-center py-16">
              <div className="text-center">
                <div className="mx-auto h-10 w-10 animate-spin rounded-full border-2 border-amber-200 border-t-amber-500" />
                <p className="mt-3 text-sm text-muted-foreground">Loading compliance data...</p>
              </div>
            </div>
          ) : filteredTeachers.length === 0 ? (
            <div className="rounded-xl border border-dashed border-amber-200 bg-amber-50/40 p-10 text-center">
              <p className="text-sm text-muted-foreground">
                {searchTerm
                  ? 'No teachers match your search.'
                  : 'No teachers are available for this department term view yet.'}
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredTeachers.map((teacher) => {
                const reminderKey = `teacher-${teacher.user_id}`;
                const canSendReminder = Boolean(teacher.needs_follow_up);

                return (
                  <div
                    key={teacher.user_id}
                    className="rounded-xl border border-amber-200 bg-amber-50/30 p-4 shadow-sm"
                  >
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-lg font-semibold text-gray-900">
                            {teacher.first_name} {teacher.last_name}
                          </h3>
                          <Badge variant={getTeacherStatusVariant(teacher.teacher_status)}>
                            {teacher.teacher_status_label}
                          </Badge>
                        </div>

                        <p className="text-sm text-muted-foreground">{teacher.email}</p>

                        <div className="flex flex-wrap gap-3 text-sm text-amber-900">
                          <span>
                            Submitted: {teacher.submitted_exam_count} / {teacher.expected_exam_count}
                          </span>
                          <span>
                            Created: {teacher.created_exam_count} / {teacher.expected_exam_count}
                          </span>
                          <span>Incomplete: {teacher.incomplete_exam_count}</span>
                        </div>

                        {teacher.exam_title && (
                          <p className="text-sm text-muted-foreground">
                            Latest exam: {teacher.exam_title}
                          </p>
                        )}

                        {teacher.exam_status_label && (
                          <p className="text-sm text-muted-foreground">
                            Exam status for this term: {teacher.exam_status_label}
                          </p>
                        )}
                      </div>

                      <Button
                        type="button"
                        variant="outline"
                        className="border-amber-300 text-amber-800 hover:bg-amber-100"
                        disabled={!canSendReminder || sendingReminderKey === reminderKey}
                        onClick={() => sendReminder([teacher.user_id], reminderKey)}
                      >
                        <BellRing className="mr-2 h-4 w-4" />
                        {sendingReminderKey === reminderKey ? 'Sending...' : 'Send Reminder'}
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default DepartmentExamCompliance;
