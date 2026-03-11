import React, { useState, useEffect, useRef } from 'react';
import ReactDOM from 'react-dom';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '../../components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '../../components/ui/select';
import { Badge } from '../../components/ui/badge';

import { toast } from 'react-hot-toast';
import api from '../../utils/api';
import {
  fetchAllSavedExams,
  fetchAllTeacherExams,
  mergeExamCollections,
} from '../../utils/exams';
import {
  Search,
  Filter,
  Plus,
  FileText,
  Clock,
  Users,
  Edit3,
  Eye,
  Send,
  Trash2,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Clock3,
  Lock,
  RefreshCw,
  Calendar
} from 'lucide-react';
import './css/manageexams.css';

// Modal Component using Portal
function Modal({ isOpen, onClose, children }) {
  if (!isOpen) return null;

  return ReactDOM.createPortal(
    <div 
      className="modal-overlay"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.4)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '1rem',
        animation: 'fadeIn 0.2s ease-out'
      }}
      onClick={onClose}
    >
      <div 
        onClick={(e) => e.stopPropagation()}
        style={{
          backgroundColor: 'white',
          borderRadius: '16px',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
          width: '100%',
          maxWidth: '32rem',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          position: 'relative',
          zIndex: 10000,
          animation: 'scaleIn 0.2s ease-out'
        }}
      >
        {children}
      </div>
    </div>,
    document.body
  );
}

function ManageExams() {
  const { currentUser } = useAuth();

  const [exams, setExams] = useState([]);
  const [filteredExams, setFilteredExams] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [departments, setDepartments] = useState([]); 

  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [subjectFilter, setSubjectFilter] = useState('all');

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // State for Submit Modal
  const [submitDialogOpen, setSubmitDialogOpen] = useState(false);
  const [selectedExam, setSelectedExam] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitData, setSubmitData] = useState({
    department_id: '',
    instructor_notes: ''
  });

  // State for Re-Use Modal
  const [reuseDialogOpen, setReuseDialogOpen] = useState(false);
  const [reuseExam, setReuseExam] = useState(null);
  const [isReusing, setIsReusing] = useState(false);

  // Ref to prevent multiple fetches in Strict Mode
  const hasFetched = useRef(false);

  useEffect(() => {
    if (currentUser?.user_id && !hasFetched.current) {
      hasFetched.current = true;
      fetchExams();
      fetchDepartments();
    }
  }, [currentUser]);

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (submitDialogOpen) {
      document.body.style.overflow = 'hidden';
      
      const styleId = 'modal-select-fix';
      if (!document.getElementById(styleId)) {
        const style = document.createElement('style');
        style.id = styleId;
        style.textContent = `
          [data-radix-popper-content-wrapper] {
            z-index: 10001 !important;
          }
        `;
        document.head.appendChild(style);
      }
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [submitDialogOpen]);

  const fetchExams = async () => {
    if (!currentUser?.user_id) return;

    setIsLoading(true);
    setError(null);

    try {
      let draftExams = [];
      let teacherExams = [];
      let allExams = [];
      
      // ⭐ STEP 1: Fetch saved/draft exams
      try {
        console.log('📂 Fetching saved exams...');
        draftExams = await fetchAllSavedExams();
        allExams = [...draftExams];
        console.log(`📂 Found ${draftExams.length} draft exams`);
      } catch (savedErr) {
        console.warn('⚠️ Could not fetch saved exams:', savedErr.message);
      }
      
      // ⭐ STEP 2: Fetch ALL exams by teacher
      try {
        console.log(`👨‍🏫 Fetching all teacher exams for user ${currentUser.user_id}...`);
        teacherExams = await fetchAllTeacherExams(currentUser.user_id);
        console.log(`👨‍🏫 Found ${teacherExams.length} total teacher exams`);
        
        // ⭐ STEP 3: Filter out drafts
        const nonDraftExams = teacherExams.filter(exam => 
          exam.admin_status !== 'draft'
        );
        console.log(`✅ Filtered to ${nonDraftExams.length} non-draft exams`);
        
        // ⭐ STEP 4: Combine draft + non-draft exams
        allExams = mergeExamCollections(draftExams, nonDraftExams);
        
      } catch (teacherErr) {
        console.error('❌ Error fetching teacher exams:', teacherErr);
      }
      
      // ⭐ STEP 5: Log status breakdown
      console.log(`📊 Total exams loaded: ${allExams.length}`);
      console.log('📋 Status breakdown:', {
        draft: allExams.filter(e => e.admin_status === 'draft').length,
        pending: allExams.filter(e => e.admin_status === 'pending').length,
        approved: allExams.filter(e => e.admin_status === 'approved').length,
        revision_required: allExams.filter(
          e => e.admin_status === 'revision_required' || e.admin_status === 'rejected'
        ).length,
        revised: allExams.filter(e => e.admin_status === 'Re-Used').length,
      });
      
      setExams(allExams);
      setFilteredExams(allExams);

      // Extract unique subjects
      const uniqueSubjects = Array.from(
        new Set(allExams.map(e => e.subject_name).filter(Boolean))
      );
      setSubjects(uniqueSubjects);
      
    } catch (err) {
      console.error('❌ Error in fetchExams:', err);
      setError('Failed to load exams');
      toast.error('Failed to load exams');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchDepartments = async () => {
    try {
      const res = await api.get('/departments');
      setDepartments(res.data.departments || []);
    } catch (err) {
      console.error("Failed to load departments", err);
    }
  };

  const normalizeExamStatus = (status) => {
    if (!status) return 'draft';
    if (status === 'rejected') return 'revision_required';
    return status;
  };

  useEffect(() => {
    let result = [...exams]; 

    if (searchTerm.trim() !== '') {
      const term = searchTerm.toLowerCase();
      result = result.filter(e =>
        e.title?.toLowerCase().includes(term) ||
        e.subject_name?.toLowerCase().includes(term)
      );
    }

    if (statusFilter !== 'all') {
      result = result.filter(e => normalizeExamStatus(e.admin_status) === statusFilter);
    }

    if (subjectFilter !== 'all') {
      result = result.filter(e => e.subject_name === subjectFilter);
    }

    setFilteredExams(result);
  }, [exams, searchTerm, statusFilter, subjectFilter]);

  const handleDeleteExam = async (examId, examStatus) => {
    if (examStatus === 'approved') {
      toast.error('Cannot delete approved exams');
      return;
    }

    if (!window.confirm('Are you sure you want to delete this exam? This action cannot be undone.')) return;

    try {
      await api.delete(`/exams/${examId}`);
      setExams(prev => prev.filter(e => e.exam_id !== examId));
      toast.success('Exam deleted successfully');
    } catch (err) {
      console.error('Delete error:', err);
      toast.error('Failed to delete exam');
    }
  };

  const handleEditClick = (exam) => {
    if (exam.admin_status === 'approved') {
      toast.error('Cannot edit approved exams', {
        duration: 3000,
        icon: '🔒',
      });
      return false;
    }
    return true;
  };

  const openSubmitModal = (exam) => {
    setSelectedExam(exam);
    setSubmitData({
      department_id: '',
      instructor_notes: ''
    });
    setSubmitDialogOpen(true);
  };

  const closeSubmitModal = () => {
    setSubmitDialogOpen(false);
    setSelectedExam(null);
    setSubmitData({
      department_id: '',
      instructor_notes: ''
    });
  };

  const handleConfirmSubmit = async () => {
    if (!submitData.department_id) {
      toast.error("Please select a department");
      return;
    }

    if (!selectedExam) return;

    setIsSubmitting(true);
    try {
      await api.post(`/exams/${selectedExam.exam_id}/submit`, submitData);
      toast.success('Exam submitted for approval!');
      closeSubmitModal();
      
      // Reset ref and re-fetch
      hasFetched.current = false;
      fetchExams();
    } catch (err) {
      console.error('Submit error:', err);
      toast.error(err.response?.data?.message || 'Failed to submit exam');
    } finally {
      setIsSubmitting(false);
    }
  };

  // ── Re-Use helpers ──────────────────────────────────────────────────────────

  const THREE_YEARS_MS = 3 * 365.25 * 24 * 60 * 60 * 1000;

  const getReuseEligibility = (exam) => {
    if (exam.admin_status !== 'approved') return { eligible: false, reason: 'not_approved' };
    if (!exam.reviewed_at) return { eligible: false, reason: 'no_date' };

    const approvedMs = new Date(exam.reviewed_at).getTime();
    const elapsedMs = Date.now() - approvedMs;

    if (elapsedMs >= THREE_YEARS_MS) return { eligible: true };

    const eligibleDate = new Date(approvedMs + THREE_YEARS_MS);
    const remainingMs = THREE_YEARS_MS - elapsedMs;
    const remainingYears = remainingMs / (365.25 * 24 * 60 * 60 * 1000);
    const remainingLabel =
      remainingYears >= 1
        ? `${remainingYears.toFixed(1)} year${remainingYears >= 2 ? 's' : ''}`
        : `${Math.ceil(remainingMs / (30 * 24 * 60 * 60 * 1000))} month(s)`;

    return { eligible: false, reason: 'too_soon', eligibleDate, remainingLabel };
  };

  const openReuseModal = (exam) => {
    setReuseExam(exam);
    setReuseDialogOpen(true);
  };

  const closeReuseModal = () => {
    setReuseDialogOpen(false);
    setReuseExam(null);
  };

  const handleConfirmReuse = async () => {
    if (!reuseExam) return;
    setIsReusing(true);
    try {
      const res = await api.post(`/exams/${reuseExam.exam_id}/reuse`);
      toast.success(res.data.message || 'Exam re-used successfully! A new draft has been created.');
      closeReuseModal();
      hasFetched.current = false;
      fetchExams();
    } catch (err) {
      toast.error(err.response?.data?.message || 'Failed to re-use exam');
    } finally {
      setIsReusing(false);
    }
  };

  // ────────────────────────────────────────────────────────────────────────────

  const getStatusBadge = (status) => {
    const statusConfig = {
      draft: {
        label: 'Draft',
        variant: 'secondary',
        icon: Edit3,
        className: 'bg-gray-100 text-gray-700 border-gray-200'
      },
      pending: {
        label: 'Pending',
        variant: 'outline',
        icon: Clock3,
        className: 'bg-blue-50 text-blue-700 border-blue-200'
      },
      approved: {
        label: 'Approved',
        variant: 'default',
        icon: CheckCircle2,
        className: 'bg-green-50 text-green-700 border-green-200'
      },
      revision_required: {
        label: 'Revision Required',
        variant: 'destructive',
        icon: AlertCircle,
        className: 'bg-orange-50 text-orange-700 border-orange-200'
      },
      'Re-Used': {
        label: 'Revised',
        variant: 'outline',
        icon: CheckCircle2,
        className: 'bg-emerald-50 text-emerald-700 border-emerald-200'
      }
    };

    const normalizedStatus = normalizeExamStatus(status);
    const config = statusConfig[normalizedStatus] || statusConfig.draft;
    const Icon = config.icon;

    return (
      <Badge variant={config.variant} className={`${config.className} flex items-center gap-1 px-2.5 py-1 font-medium border`}>
        <Icon className="h-3 w-3" />
        {config.label}
      </Badge>
    );
  };

  const canEdit = (exam) => {
    return exam.admin_status !== 'approved';
  };

  const canDelete = (exam) => {
    return exam.admin_status !== 'approved';
  };

  const totalExamsCount = exams.length;
  const draftCount = exams.filter((e) => normalizeExamStatus(e.admin_status) === 'draft').length;
  const pendingCount = exams.filter((e) => normalizeExamStatus(e.admin_status) === 'pending').length;
  const approvedCount = exams.filter((e) => normalizeExamStatus(e.admin_status) === 'approved').length;
  const revisionCount = exams.filter((e) => normalizeExamStatus(e.admin_status) === 'revision_required').length;

  if (isLoading) {
    return (
      <div className="flex flex-col justify-center items-center min-h-[60vh]">
        <div className="relative">
          <div className="animate-spin rounded-full h-16 w-16 border-4 border-gray-200 border-t-yellow-500"></div>
          <div className="absolute inset-0 flex items-center justify-center">
            <FileText className="h-6 w-6 text-yellow-500" />
          </div>
        </div>
        <p className="mt-4 text-gray-600 font-medium">Loading your exams...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
        <div className="w-16 h-16 bg-red-50 rounded-full flex items-center justify-center mb-4">
          <AlertCircle className="h-8 w-8 text-red-500" />
        </div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Failed to Load Exams</h3>
        <p className="text-gray-600 mb-6 max-w-md">{error}</p>
        <Button onClick={() => {
          hasFetched.current = false;
          fetchExams();
        }} className="bg-yellow-500 hover:bg-yellow-600 text-white">
          Try Again
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6 bg-gradient-to-b from-amber-50/20 to-white rounded-xl p-1">
      {/* Header */}
      <div className="rounded-xl border border-amber-200 bg-white shadow-sm p-5">
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
          <div className="space-y-2">
            <h1 className="text-3xl font-bold text-amber-900 tracking-tight">Manage Exams</h1>
            <p className="text-amber-800 text-base">
              View and organize your exam collection
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              <Badge variant="outline" className="border-amber-300 bg-amber-50 text-amber-800 text-xs">Total: {totalExamsCount}</Badge>
              <Badge variant="outline" className="border-gray-300 bg-gray-50 text-gray-700 text-xs">Draft: {draftCount}</Badge>
              <Badge variant="outline" className="border-blue-300 bg-blue-50 text-blue-700 text-xs">Pending: {pendingCount}</Badge>
              <Badge variant="outline" className="border-green-300 bg-green-50 text-green-700 text-xs">Approved: {approvedCount}</Badge>
              <Badge variant="outline" className="border-orange-300 bg-orange-50 text-orange-700 text-xs">Revision: {revisionCount}</Badge>
            </div>
          </div>
          <Link to="/teacher/create-exam">
            <Button className="bg-amber-500 hover:bg-amber-600 text-white font-semibold shadow-sm hover:shadow-md transition-all duration-200 px-6">
              <Plus className="h-4 w-4 mr-2" />
              Create Exam
            </Button>
          </Link>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-amber-200 p-5 shadow-sm">
        <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1.2fr)_0.9fr_0.9fr] gap-4">
          <div>
            <div className="relative">
              <Input
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                placeholder="Search exams..."
                className="pl-10 h-11 border-amber-200 focus:border-amber-500 focus:ring-amber-500"
              />
            </div>
          </div>

          <div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="h-11 border-amber-200 focus:border-amber-500 focus:ring-amber-500">
                <div className="flex items-center gap-2">
                  <Filter className="h-4 w-4 text-amber-500" />
                  <SelectValue placeholder="All Status" />
                </div>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="draft">Draft</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="approved">Approved</SelectItem>
                <SelectItem value="revision_required">Revision Required</SelectItem>
                <SelectItem value="Re-Used">Revised</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Select value={subjectFilter} onValueChange={setSubjectFilter}>
              <SelectTrigger className="h-11 border-amber-200 focus:border-amber-500 focus:ring-amber-500">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-amber-500" />
                  <SelectValue placeholder="All Subjects" />
                </div>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Subjects</SelectItem>
                {subjects.map(s => (
                  <SelectItem key={s} value={s}>{s}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {(searchTerm || statusFilter !== 'all' || subjectFilter !== 'all') && (
          <div className="mt-4 pt-4 border-t border-amber-200 flex items-center gap-2 flex-wrap">
            <span className="text-sm text-amber-800 font-medium">Active filters:</span>
            {searchTerm && (
              <Badge variant="secondary" className="gap-1 bg-amber-50 text-amber-800 border border-amber-200">
                Search: {searchTerm}
                <button onClick={() => setSearchTerm('')} className="ml-1 hover:bg-amber-200 rounded-full p-0.5">
                  <XCircle className="h-3 w-3" />
                </button>
              </Badge>
            )}
            {statusFilter !== 'all' && (
              <Badge variant="secondary" className="gap-1 bg-amber-50 text-amber-800 border border-amber-200">
                Status: {statusFilter}
                <button onClick={() => setStatusFilter('all')} className="ml-1 hover:bg-amber-200 rounded-full p-0.5">
                  <XCircle className="h-3 w-3" />
                </button>
              </Badge>
            )}
            {subjectFilter !== 'all' && (
              <Badge variant="secondary" className="gap-1 bg-amber-50 text-amber-800 border border-amber-200">
                Subject: {subjectFilter}
                <button onClick={() => setSubjectFilter('all')} className="ml-1 hover:bg-amber-200 rounded-full p-0.5">
                  <XCircle className="h-3 w-3" />
                </button>
              </Badge>
            )}
            <button 
              onClick={() => {
                setSearchTerm('');
                setStatusFilter('all');
                setSubjectFilter('all');
              }}
              className="text-sm text-amber-700 hover:text-amber-800 font-medium ml-auto"
            >
              Clear all
            </button>
          </div>
        )}
      </div>

      {/* Exam Cards */}
      {filteredExams.length === 0 ? (
        <Card className="border-2 border-dashed border-amber-300 bg-white shadow-none">
          <CardContent className="py-16 text-center">
            <div className="w-20 h-20 bg-amber-50 rounded-full flex items-center justify-center mx-auto mb-4">
              <FileText className="h-10 w-10 text-amber-500" />
            </div>
            <h3 className="text-lg font-semibold text-amber-900 mb-2">
              {exams.length === 0 ? 'No exams yet' : 'No matching exams'}
            </h3>
            <p className="text-amber-800 mb-6 max-w-sm mx-auto">
              {exams.length === 0 
                ? 'Get started by creating your first exam. It only takes a few minutes!' 
                : 'Try adjusting your filters to find what you\'re looking for'}
            </p>
            {exams.length === 0 && (
              <Link to="/teacher/create-exam">
                <Button className="bg-amber-500 hover:bg-amber-600 text-white font-semibold">
                  <Plus className="h-4 w-4 mr-2" />
                  Create Your First Exam
                </Button>
              </Link>
            )}
          </CardContent>
        </Card>
      ) : (() => {
        const isMidterm = (e) => (e.category_name || '').toLowerCase().includes('midterm');
        const isFinal   = (e) => (e.category_name || '').toLowerCase().includes('final');
        const groups = [
          { key: 'midterm', label: 'Midterm Exams', exams: filteredExams.filter(isMidterm) },
          { key: 'final',   label: 'Final Exams',   exams: filteredExams.filter(isFinal) },
          { key: 'other',   label: 'Other Exams',   exams: filteredExams.filter(e => !isMidterm(e) && !isFinal(e)) },
        ].filter(g => g.exams.length > 0);
        const showHeaders = groups.some(g => g.key !== 'other') || groups.length > 1;
        return (
          <div className="space-y-10">
            {groups.map(({ key, label, exams: groupExams }) => (
              <div key={key}>
                {showHeaders && (
                  <div className="flex items-center gap-3 mb-5">
                    <div className="w-1 h-6 bg-amber-500 rounded-full" />
                    <h2 className="text-xl font-bold text-amber-900">{label}</h2>
                    <span className="text-sm text-amber-700 font-normal">({groupExams.length})</span>
                  </div>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {groupExams.map(exam => (
                    <Card
                      key={exam.exam_id}
                      className="group hover:shadow-lg transition-all duration-300 border-amber-200 hover:border-amber-400 bg-white flex flex-col overflow-hidden rounded-xl"
                    >
              <CardHeader className="space-y-3 pb-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <CardTitle className="text-lg font-bold text-amber-950 line-clamp-2 group-hover:text-amber-700 transition-colors">
                      {exam.title}
                    </CardTitle>
                  </div>
                  {getStatusBadge(exam.admin_status || 'draft')}
                </div>
                
                <CardDescription className="flex items-center gap-2 text-sm text-amber-800">
                  <FileText className="h-4 w-4 text-amber-500 flex-shrink-0" />
                  <span className="truncate">{exam.subject_name || ''}</span>
                </CardDescription>
              </CardHeader>

              <CardContent className="flex-1 space-y-4 pb-4">
                <div className="grid grid-cols-3 gap-3">
                  <div className="text-center p-3 bg-amber-50/50 rounded-lg border border-amber-200">
                    <div className="flex items-center justify-center mb-1">
                      <FileText className="h-4 w-4 text-amber-700" />
                    </div>
                    <div className="text-xl font-bold text-amber-900">{exam.total_questions}</div>
                    <div className="text-xs text-amber-700 mt-0.5">Questions</div>
                  </div>
                  
                  <div className="text-center p-3 bg-amber-50/50 rounded-lg border border-amber-200">
                    <div className="flex items-center justify-center mb-1">
                      <Clock className="h-4 w-4 text-amber-700" />
                    </div>
                    <div className="text-xl font-bold text-amber-900">{exam.duration_minutes}</div>
                    <div className="text-xs text-amber-700 mt-0.5">Minutes</div>
                  </div>
                  
                  <div className="text-center p-3 bg-amber-50/50 rounded-lg border border-amber-200">
                    <div className="flex items-center justify-center mb-1">
                      <Users className="h-4 w-4 text-amber-700" />
                    </div>
                    <div className="text-xl font-bold text-amber-900">{exam.passing_score}%</div>
                    <div className="text-xs text-amber-700 mt-0.5">Passing</div>
                  </div>
                </div>

                {exam.created_at && (
                  <div className="text-xs text-gray-500 flex items-center gap-1">
                    <Clock3 className="h-3 w-3" />
                    Created {new Date(exam.created_at).toLocaleDateString('en-US', { 
                      month: 'short', 
                      day: 'numeric', 
                      year: 'numeric' 
                    })}
                  </div>
                )}

                {exam.admin_status === 'approved' && (() => {
                  const { eligible, remainingLabel, eligibleDate } = getReuseEligibility(exam);
                  return (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2 p-2 bg-green-50 border border-green-200 rounded-lg">
                        <Lock className="h-3.5 w-3.5 text-green-600 flex-shrink-0" />
                        <p className="text-xs text-green-700 font-medium">
                          This exam is locked and cannot be edited
                        </p>
                      </div>
                      {eligible ? (
                        <div className="flex items-center gap-2 p-2 bg-purple-50 border border-purple-200 rounded-lg">
                          <RefreshCw className="h-3.5 w-3.5 text-purple-600 flex-shrink-0" />
                          <p className="text-xs text-purple-700 font-medium">
                            Eligible for Re-Use — approved 3+ years ago
                          </p>
                        </div>
                      ) : eligibleDate ? (
                        <div className="flex items-center gap-2 p-2 bg-gray-50 border border-gray-200 rounded-lg">
                          <Calendar className="h-3.5 w-3.5 text-gray-500 flex-shrink-0" />
                          <p className="text-xs text-gray-500">
                            Re-Use eligible in {remainingLabel} ({eligibleDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })})
                          </p>
                        </div>
                      ) : null}
                    </div>
                  );
                })()}
              </CardContent>

              <CardContent className="pt-0 pb-4 border-t border-gray-100">
                <div className="flex gap-2 flex-wrap">
                  {canEdit(exam) ? (
                    <Link to={`/teacher/edit-exam/${exam.exam_id}`} className="flex-1">
                      <Button 
                        size="sm" 
                        variant="outline" 
                        className="w-full hover:bg-gray-50 hover:border-gray-300"
                      >
                        <Edit3 className="h-3.5 w-3.5 mr-1.5" />
                        Edit
                      </Button>
                    </Link>
                  ) : (
                    <Button 
                      size="sm" 
                      variant="outline" 
                      className="flex-1 cursor-not-allowed opacity-50"
                      disabled
                      onClick={() => handleEditClick(exam)}
                    >
                      <Lock className="h-3.5 w-3.5 mr-1.5" />
                      Locked
                    </Button>
                  )}
                  
                  <Link to={`/teacher/exam-preview/${exam.exam_id}`} className="flex-1">
                    <Button 
                      size="sm" 
                      variant="outline" 
                      className="w-full hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700"
                    >
                      <Eye className="h-3.5 w-3.5 mr-1.5" />
                      Preview
                    </Button>
                  </Link>
                </div>

                <div className="flex gap-2 mt-2">
                  {(!exam.admin_status || exam.admin_status === 'draft' || exam.admin_status === 'rejected' || exam.admin_status === 'revision_required' || exam.admin_status === 'Re-Used') && (
                    <Button
                      size="sm"
                      className="flex-1 bg-blue-600 text-white hover:bg-blue-700 font-medium"
                      onClick={() => openSubmitModal(exam)}
                    >
                      <Send className="h-3.5 w-3.5 mr-1.5" />
                      Submit
                    </Button>
                  )}

                  {exam.admin_status === 'approved' && (() => {
                    const { eligible } = getReuseEligibility(exam);
                    return eligible ? (
                      <Button
                        size="sm"
                        className="flex-1 bg-purple-600 text-white hover:bg-purple-700 font-medium"
                        onClick={() => openReuseModal(exam)}
                      >
                        <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
                        Re-Use
                      </Button>
                    ) : null;
                  })()}

                  {canDelete(exam) ? (
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-red-600 hover:bg-red-50 hover:border-red-300"
                      onClick={() => handleDeleteExam(exam.exam_id, exam.admin_status)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      className="cursor-not-allowed opacity-50"
                      disabled
                      title="Cannot delete approved exams"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          ))}
        </div>
        );
      })()}

      {/* Re-Use Confirmation Modal */}
      <Modal isOpen={reuseDialogOpen} onClose={closeReuseModal}>
        <div className="px-6 py-5 border-b border-gray-200">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 bg-purple-100 rounded-full flex items-center justify-center flex-shrink-0">
              <RefreshCw className="h-5 w-5 text-purple-600" />
            </div>
            <div className="flex-1">
              <h2 className="text-xl font-semibold text-gray-900 mb-1">Re-Use Approved Exam</h2>
              <p className="text-sm text-gray-600">{reuseExam?.title}</p>
            </div>
          </div>
        </div>

        <div className="px-6 py-5 space-y-4">
          <div className="p-4 bg-purple-50 border border-purple-200 rounded-lg">
            <p className="text-sm text-purple-800 font-medium mb-1">What will happen:</p>
            <ul className="text-sm text-purple-700 space-y-1 list-disc list-inside">
              <li>A new <strong>draft</strong> copy of this exam will be created</li>
              <li>All questions will be copied to the new draft</li>
              <li>The new exam will be titled <strong>"{reuseExam?.title} (Re-Use {new Date().getFullYear()})"</strong></li>
              <li>You can then submit the new draft to the department for review</li>
            </ul>
          </div>

          {reuseExam?.reviewed_at && (
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <Calendar className="h-3.5 w-3.5" />
              <span>
                Originally approved on{' '}
                {new Date(reuseExam.reviewed_at).toLocaleDateString('en-US', {
                  month: 'long', day: 'numeric', year: 'numeric'
                })}
              </span>
            </div>
          )}
        </div>

        <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex justify-end gap-3 rounded-b-2xl">
          <Button
            variant="outline"
            onClick={closeReuseModal}
            disabled={isReusing}
            className="px-5"
          >
            Cancel
          </Button>
          <Button
            onClick={handleConfirmReuse}
            disabled={isReusing}
            className="bg-purple-600 hover:bg-purple-700 text-white px-6 font-medium"
          >
            {isReusing ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent mr-2"></div>
                Creating Copy...
              </>
            ) : (
              <>
                <RefreshCw className="h-4 w-4 mr-2" />
                Confirm Re-Use
              </>
            )}
          </Button>
        </div>
      </Modal>

      {/* Submit for Approval Modal */}
      <Modal isOpen={submitDialogOpen} onClose={closeSubmitModal}>
        <div className="px-6 py-5 border-b border-gray-200">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0">
              <Send className="h-5 w-5 text-blue-600" />
            </div>
            <div className="flex-1">
              <h2 className="text-xl font-semibold text-gray-900 mb-1">
                Submit for Approval
              </h2>
              <p className="text-sm text-gray-600">
                {selectedExam?.title}
              </p>
            </div>
          </div>
        </div>

        <div className="px-6 py-5 space-y-5 overflow-y-auto max-h-[60vh]">
          <div>
            <Label htmlFor="department" className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-1">
              Department
              <span className="text-red-500">*</span>
            </Label>
            <Select 
              value={submitData.department_id} 
              onValueChange={(val) => setSubmitData({...submitData, department_id: val})}
            >
              <SelectTrigger 
                id="department" 
                className="h-11 border-gray-300 focus:border-blue-500 focus:ring-blue-500"
              >
                <SelectValue placeholder="Select a department" />
              </SelectTrigger>
              <SelectContent style={{ zIndex: 10001 }} position="popper" sideOffset={5}>
                {departments.length > 0 ? (
                  departments.map(dept => (
                    <SelectItem key={dept.department_id} value={String(dept.department_id)}>
                      {dept.department_name}
                    </SelectItem>
                  ))
                ) : (
                  <SelectItem value="none" disabled>No departments available</SelectItem>
                )}
              </SelectContent>
            </Select>
            <p className="text-xs text-gray-500 mt-1.5">
              Choose the department that will review this exam
            </p>
          </div>

          <div>
            <Label htmlFor="notes" className="text-sm font-semibold text-gray-900 mb-2 block">
              Instructor Notes
              <span className="text-gray-500 font-normal ml-1">(Optional)</span>
            </Label>
            <textarea
              id="notes"
              className="flex min-h-[100px] w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              placeholder="Add any specific instructions, context, or notes for the reviewers..."
              value={submitData.instructor_notes}
              onChange={(e) => setSubmitData({...submitData, instructor_notes: e.target.value})}
              rows={4}
            />
          </div>
        </div>

        <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex justify-end gap-3 rounded-b-2xl">
          <Button 
            variant="outline" 
            onClick={closeSubmitModal}
            disabled={isSubmitting}
            className="px-5"
          >
            Cancel
          </Button>
          <Button 
            onClick={handleConfirmSubmit} 
            disabled={isSubmitting || !submitData.department_id}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 font-medium"
          >
            {isSubmitting ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent mr-2"></div>
                Submitting...
              </>
            ) : (
              <>
                <Send className="h-4 w-4 mr-2" />
                Submit Exam
              </>
            )}
          </Button>
        </div>
      </Modal>
    </div>
  );
}

export default ManageExams;
