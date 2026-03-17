import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import './css/createexam.css';
import { Label } from '../../components/ui/label';
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  CardDescription,
} from '../../components/ui/card';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import { Textarea } from '../../components/ui/textarea';
import {
  Upload, FileText, X, AlertCircle, CheckCircle,
  BarChart3, Loader2, BookOpen, Clock, Target,
  ChevronDown, ChevronUp,
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import api from '../../utils/api';
import { useAuth } from '../../context/AuthContext';
import { Progress } from '../../components/ui/progress';
import QuestionTypeConfigWithDifficulty from '../../components/QuestionTypeConfigWithDifficulty';
import {
  clampTeachingHours,
  COVERAGE_REFERENCE_TEXT,
  COVERAGE_SCALE_HOURS,
  formatCoveragePercent,
  formatTeachingHours,
  TERM_COVERAGE_HINT,
  toCoveragePercent,
} from '../../utils/moduleCoverage';

const ACTIVE_MODULE_STATUSES = new Set(['pending', 'processing']);
const DEFAULT_QUESTION_TYPES_DETAILS = [
  { type: 'multiple_choice', difficulty: 'lots', points: 1, count: 5, description: '' }
];
const MODULE_STATUS_POLL_INTERVAL_MS = 3000;

const toTitleCase = (value) => {
  if (typeof value !== 'string') return '';
  return value.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
};

const normalizeModuleStatus = (status) => {
  const normalized = String(status || 'pending').trim().toLowerCase();
  return ['pending', 'processing', 'completed', 'failed'].includes(normalized)
    ? normalized
    : 'pending';
};

const mergeSelectedModulesWithLatest = (latestModules, selectedSnapshot = []) => {
  const latestById = new Map(
    (latestModules || []).map((module) => [Number(module.module_id), module])
  );

  return (selectedSnapshot || [])
    .map((selectedModule) => {
      const moduleId = Number(selectedModule?.module_id);
      const latestModule = latestById.get(moduleId);
      if (!latestModule) return null;

      return {
        ...latestModule,
        teachingHours: clampTeachingHours(selectedModule?.teachingHours),
      };
    })
    .filter(Boolean);
};

const getModuleStatusMeta = (module) => {
  const status = normalizeModuleStatus(module?.processing_status);

  if (status === 'completed') {
    if ((module?.question_count ?? 0) > 0) {
      return {
        status,
        shortLabel: `${module.question_count} questions`,
        detailLabel: 'Ready to use',
      };
    }

    return {
      status,
      shortLabel: 'Ready',
      detailLabel: 'Completed with no generated questions yet',
    };
  }

  if (status === 'failed') {
    return {
      status,
      shortLabel: 'Failed',
      detailLabel: 'Processing failed. Re-upload this module if needed.',
    };
  }

  if (status === 'processing') {
    return {
      status,
      shortLabel: 'Processing...',
      detailLabel: 'Module processing is still in progress.',
    };
  }

  return {
    status,
    shortLabel: 'Pending...',
    detailLabel: 'Upload finished. Waiting for processing to start.',
  };
};

  const EXAM_ERROR_FIELD_LABELS = {
    title: 'Exam Title',
    category_id: 'Exam Category',
    minutesduration_: 'Duration',
    passing_score: 'Passing Score',
    score_limit: 'Score Limit',
    num_questions: 'Total Questions',
    question_types_details: 'Question Type Settings',
    modules: 'Selected Modules',
    total_hours: 'Total Module Coverage',
    allocated_minutes: 'Allocated Time',
  };
const HEAVY_GENERATION_QUESTION_THRESHOLD = 30;
const HEAVY_GENERATION_MESSAGE =
  'This module contains a large amount of content. Loading may take a few moments. Please wait.';

const summarizeValidationErrors = (errors) => {
  if (!errors || typeof errors !== 'object') return '';
  const entries = [];

  Object.entries(errors).forEach(([field, value]) => {
    const label = EXAM_ERROR_FIELD_LABELS[field] || field;
    if (Array.isArray(value)) {
      value.forEach((msg) => entries.push(`${label}: ${msg}`));
      return;
    }
    if (typeof value === 'string') {
      entries.push(`${label}: ${value}`);
      return;
    }
    if (value && typeof value === 'object') {
      entries.push(`${label}: invalid value`);
    }
  });

  return entries.slice(0, 4).join(' | ');
};

function CreateExam({ mode = 'teacher' }) {
  const navigate = useNavigate();
  const { currentUser } = useAuth();
  const userRole = currentUser?.role?.toLowerCase();
  const isDepartmentMode = mode === 'department' || userRole === 'department_head' || userRole === 'department';
  const [isLoading, setIsLoading] = useState(false);
  const [modules, setModules] = useState([]);
  const [categories, setCategories] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [generatedExam, setGeneratedExam] = useState(null);
  const [showTOS, setShowTOS] = useState(true);
  const [selectedModules, setSelectedModules] = useState([]);

  const [targetScoreLimit, setTargetScoreLimit] = useState(50);
  const [currentQuestionCount, setCurrentQuestionCount] = useState(0);
  const [currentTotalPoints, setCurrentTotalPoints] = useState(0);
  const [limitErrors, setLimitErrors] = useState({ pointsExceeds: false, timeExceeds: false });

  const [questionTypesDetails, setQuestionTypesDetails] = useState(DEFAULT_QUESTION_TYPES_DETAILS);

  const [showUploadSection, setShowUploadSection] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [selectedSubject, setSelectedSubject] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatus, setUploadStatus] = useState('idle');
  const [currentFileIndex, setCurrentFileIndex] = useState(0);
  const [generationProgress, setGenerationProgress] = useState(0);
  const generationTimer = useRef(null);
  const previewRef = useRef(null);
  const [status, setStatus] = useState({ api: 'checking', message: 'Checking connection…' });
  const showHeavyGenerationNotice =
    isLoading &&
    uploadStatus !== 'uploading' &&
    currentQuestionCount >= HEAVY_GENERATION_QUESTION_THRESHOLD;
  const selectedModulesRef = useRef([]);
  const pendingSelectedModulesRef = useRef([]);
  const [selectedModulesReady, setSelectedModulesReady] = useState(false);
  const selectedModulesDraftKey = currentUser?.user_id
    ? `create-exam-selected-modules:${isDepartmentMode ? 'department' : 'teacher'}:${currentUser.user_id}`
    : null;

  const { register, handleSubmit, setValue, watch, formState: { errors } } = useForm();
  const formatSubjectLabel = (subject) => subject?.subject_name || 'Unnamed Subject';

  const groupedSubjects = useMemo(() => {
    const normalizedDepartments = (departments || [])
      .map((department) => ({
        id: department?.department_id ?? department?.id ?? null,
        name: String(department?.department_name || department?.name || '').trim()
      }))
      .filter((department) => department.name.length > 0);

    const groups = normalizedDepartments.map((department) => ({
      key: `dep-${department.id ?? department.name.toLowerCase()}`,
      departmentName: department.name,
      subjects: []
    }));

    const groupsByDepartmentId = new Map();
    const groupsByDepartmentName = new Map();

    normalizedDepartments.forEach((department, idx) => {
      const group = groups[idx];
      if (department.id !== null && department.id !== undefined && department.id !== '') {
        groupsByDepartmentId.set(Number(department.id), group);
      }
      groupsByDepartmentName.set(department.name.toLowerCase(), group);
    });

    subjects.forEach((subject) => {
      let group = null;
      if (subject?.department_id !== null && subject?.department_id !== undefined) {
        group = groupsByDepartmentId.get(Number(subject.department_id)) || null;
      }
      if (!group && subject?.department_name) {
        group = groupsByDepartmentName.get(String(subject.department_name).trim().toLowerCase()) || null;
      }

      if (!group) {
        const fallbackName = String(subject?.department_name || 'Other Department').trim();
        const fallbackKey = fallbackName.toLowerCase();
        group = groupsByDepartmentName.get(fallbackKey) || null;
        if (!group) {
          group = {
            key: `fallback-${fallbackKey.replace(/\s+/g, '-')}`,
            departmentName: fallbackName,
            subjects: []
          };
          groups.push(group);
          groupsByDepartmentName.set(fallbackKey, group);
        }
      }

      group.subjects.push(subject);
    });

    return groups;
  }, [departments, subjects]);

  const subjectsById = useMemo(() => {
    const lookup = new Map();
    (subjects || []).forEach((subject) => {
      const sid = Number(subject?.subject_id);
      if (Number.isFinite(sid)) lookup.set(sid, subject);
    });
    return lookup;
  }, [subjects]);

  const watchedDuration = watch('duration_minutes');
  const watchedPassing  = watch('passing_score');
  const totalDurationMin = parseInt(watchedDuration) || 0;
  const durationValue    = Number.isFinite(watchedDuration) ? watchedDuration : '';
  const passingValue     = Number.isFinite(watchedPassing)  ? watchedPassing  : '';
  const scoreLimitValue  = targetScoreLimit === 0 ? '' : targetScoreLimit;
  const durationError    = durationValue !== '' && (durationValue < 1 || durationValue > 150);
  const passingError     = passingValue  !== '' && (passingValue  < 1 || passingValue  > 100);
  const scoreLimitError  = scoreLimitValue !== '' && (scoreLimitValue < 1 || scoreLimitValue > 150);

  const clampDuration = (v) => { const n = parseInt(v) || 0; if (n <= 0) return ''; return Math.min(n, 150); };
  const clampPassing  = (v) => { const n = parseInt(v) || 0; if (n <= 0) return ''; return Math.min(n, 100); };

  // Derived totals
  useEffect(() => {
    const totalCount  = questionTypesDetails.reduce((s, q) => s + (q.count   || 0), 0);
    const totalPoints = questionTypesDetails.reduce((s, q) => s + ((q.count || 0) * (q.points || 0)), 0);
    const totalTime   = questionTypesDetails.reduce((s, q) => s + (q.minutes || 0), 0);
    setCurrentQuestionCount(totalCount);
    setCurrentTotalPoints(totalPoints);
    setValue('num_questions', totalCount);
    setLimitErrors({
      pointsExceeds: targetScoreLimit > 0 && totalPoints !== targetScoreLimit,
      timeExceeds:   totalDurationMin > 0 && totalTime > totalDurationMin,
    });
  }, [questionTypesDetails, targetScoreLimit, totalDurationMin, setValue]);

  useEffect(() => {
    selectedModulesRef.current = selectedModules;
  }, [selectedModules]);

  useEffect(() => {
    setSelectedModulesReady(false);

    if (!selectedModulesDraftKey) {
      pendingSelectedModulesRef.current = [];
      selectedModulesRef.current = [];
      setSelectedModules([]);
      return;
    }

    try {
      const rawDraft = sessionStorage.getItem(selectedModulesDraftKey);
      const parsedDraft = rawDraft ? JSON.parse(rawDraft) : [];
      pendingSelectedModulesRef.current = Array.isArray(parsedDraft)
        ? parsedDraft
            .map((module) => ({
              module_id: Number(module?.module_id),
              teachingHours: clampTeachingHours(module?.teachingHours),
            }))
            .filter((module) => Number.isFinite(module.module_id))
        : [];
    } catch (error) {
      console.error('Failed to restore selected modules draft:', error);
      pendingSelectedModulesRef.current = [];
    }

    selectedModulesRef.current = [];
    setSelectedModules([]);
  }, [selectedModulesDraftKey]);

  useEffect(() => {
    if (!selectedModulesDraftKey || !selectedModulesReady) return;

    try {
      const draftPayload = selectedModules.map((module) => ({
        module_id: Number(module.module_id),
        teachingHours: clampTeachingHours(module.teachingHours),
      }));
      sessionStorage.setItem(selectedModulesDraftKey, JSON.stringify(draftPayload));
    } catch (error) {
      console.error('Failed to persist selected modules draft:', error);
    }
  }, [selectedModulesDraftKey, selectedModules, selectedModulesReady]);

  const syncModulesState = (serverModules, moduleIdsToSelect = []) => {
    const selectionBase = selectedModulesRef.current.length > 0
      ? selectedModulesRef.current
      : pendingSelectedModulesRef.current;
    const modulesToAutoSelect = moduleIdsToSelect
      .map((moduleId) => ({ module_id: Number(moduleId), teachingHours: 0 }))
      .filter((module) => Number.isFinite(module.module_id));
    const mergedSelection = mergeSelectedModulesWithLatest(serverModules, [
      ...selectionBase,
      ...modulesToAutoSelect,
    ]);

    pendingSelectedModulesRef.current = [];
    setModules(serverModules);
    setSelectedModules(mergedSelection);
    setSelectedModulesReady(true);
    return mergedSelection;
  };

  const fetchModulesList = async (moduleIdsToSelect = []) => {
    if (!currentUser?.user_id) return [];

    const endpoint = isDepartmentMode
      ? '/departments/modules'
      : `/modules/teacher/${currentUser.user_id}`;
    const response = await api.get(endpoint);
    const serverModules = response.data.modules || [];
    syncModulesState(serverModules, moduleIdsToSelect);
    return serverModules;
  };

  // Fetch data
  useEffect(() => {
    let active = true;

    const fetchData = async () => {
      if (!currentUser) return;
      try {
        const modulesPromise = isDepartmentMode
          ? api.get('/departments/modules')
          : api.get(`/modules/teacher/${currentUser.user_id}`);

        const subjectsPromise = api.get('/users/subjects');

        const [modulesRes, categoriesRes, subjectsRes, departmentsRes] = await Promise.all([
          modulesPromise,
          api.get('/exams/categories'),
          subjectsPromise,
          api.get('/departments'),
        ]);

        if (!active) return;

        syncModulesState(modulesRes.data.modules || []);
        setCategories(categoriesRes.data.categories || []);
        setSubjects(subjectsRes.data.subjects || []);
        setDepartments(departmentsRes.data.departments || []);
      } catch {
        if (!active) return;
        toast.error('Failed to load data');
      }
    };
    fetchData();
    return () => { active = false; };
  }, [currentUser, isDepartmentMode]);

  useEffect(() => {
    if (!currentUser?.user_id) return undefined;

    const hasProcessingModules = [...modules, ...selectedModules].some((module) =>
      ACTIVE_MODULE_STATUSES.has(normalizeModuleStatus(module?.processing_status))
    );

    if (!hasProcessingModules) return undefined;

    const timer = setInterval(() => {
      fetchModulesList().catch((error) => {
        console.error('Failed to refresh module statuses:', error);
      });
    }, MODULE_STATUS_POLL_INTERVAL_MS);

    return () => clearInterval(timer);
  }, [currentUser?.user_id, isDepartmentMode, modules, selectedModules]);

  // API status
  useEffect(() => {
    let active = true;
    const check = async () => {
      try {
        await api.get('/auth/me');
        if (active) setStatus({ api: 'online', message: 'Online · Authenticated' });
      } catch {
        if (active) setStatus({ api: 'offline', message: 'Offline or session expired' });
      }
    };
    check();
    return () => { active = false; };
  }, []);

  // Cleanup timer
  useEffect(() => () => { if (generationTimer.current) clearInterval(generationTimer.current); }, []);

  // Module teaching-hours weight uses the configured term baseline.
  const totalCoverage = selectedModules.reduce(
    (sum, module) => sum + toCoveragePercent(module.teachingHours),
    0
  );
  const totalCoverageHours = selectedModules.reduce(
    (sum, module) => sum + clampTeachingHours(module.teachingHours),
    0
  );

  const moduleQuestionTargets = useMemo(() => {
    if (!selectedModules.length || currentQuestionCount <= 0) return {};

    const weightedModules = selectedModules.map((module) => {
      const coveragePercent = toCoveragePercent(module.teachingHours);
      return { moduleId: module.module_id, coveragePercent };
    });

    const totalPercent = weightedModules.reduce((sum, item) => sum + item.coveragePercent, 0);
    if (totalPercent <= 0) {
      return weightedModules.reduce((acc, item) => ({ ...acc, [item.moduleId]: 0 }), {});
    }

    const rawTargets = weightedModules.map((item) => (item.coveragePercent / totalPercent) * currentQuestionCount);
    const roundedTargets = rawTargets.map((value) => Math.floor(value));
    let remaining = currentQuestionCount - roundedTargets.reduce((sum, value) => sum + value, 0);

    const fractions = rawTargets
      .map((value, index) => ({ index, fraction: value - roundedTargets[index] }))
      .sort((a, b) => b.fraction - a.fraction);

    let cursor = 0;
    while (remaining > 0 && fractions.length > 0) {
      const targetIndex = fractions[cursor % fractions.length].index;
      roundedTargets[targetIndex] += 1;
      remaining -= 1;
      cursor += 1;
    }

    return weightedModules.reduce((acc, item, index) => {
      acc[item.moduleId] = roundedTargets[index];
      return acc;
    }, {});
  }, [selectedModules, currentQuestionCount]);

  // ── File handlers ──
  const handleFileChange = (e) => {
    const files = Array.from(e.target.files);
    if (!files.length) return;
    const allowed  = ['pdf', 'doc', 'docx'];
    const maxSize  = 50 * 1024 * 1024;
    const invalid  = files.filter(f => !allowed.includes(f.name.split('.').pop().toLowerCase()));
    if (invalid.length) { toast.error(`Invalid file(s): ${invalid.map(f => f.name).join(', ')}`); return; }
    const oversize = files.filter(f => f.size > maxSize);
    if (oversize.length) { toast.error(`File too large (max 50 MB): ${oversize.map(f => f.name).join(', ')}`); return; }
    setSelectedFiles(prev => [...prev, ...files]);
  };

  const removeFile = (index) => setSelectedFiles(prev => prev.filter((_, i) => i !== index));

  const uploadSingleFile = async (file, subjectId) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('subject_id', subjectId);
    return api.post('/modules/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => setUploadProgress(Math.max(1, Math.round((e.loaded * 100) / e.total))),
    });
  };

  const handleUploadModules = async () => {
    if (!selectedFiles.length) { toast.error('Please select at least one file'); return; }
    if (!selectedSubject)      { toast.error('Please select a subject'); return; }
    setIsLoading(true); setUploadStatus('uploading'); setUploadProgress(1);
    try {
      const uploadedModuleIds = [];
      for (let i = 0; i < selectedFiles.length; i++) {
        setCurrentFileIndex(i); setUploadProgress(0);
        try {
          const res = await uploadSingleFile(selectedFiles[i], selectedSubject);
          uploadedModuleIds.push(Number(res.data.module_id));
          toast.success(`✓ ${selectedFiles[i].name} uploaded`);
        } catch { toast.error(`✗ ${selectedFiles[i].name} failed`); }
      }

      if (uploadedModuleIds.length) {
        await fetchModulesList(uploadedModuleIds);
        setUploadStatus('success');
        toast.success(`${uploadedModuleIds.length} module(s) uploaded`);
        setSelectedFiles([]); setSelectedSubject(null); setShowUploadSection(false);
      } else { setUploadStatus('error'); toast.error('All uploads failed'); }
    } catch { setUploadStatus('error'); toast.error('Upload failed'); }
    finally { setIsLoading(false); setCurrentFileIndex(0); setUploadProgress(0); }
  };

  const handleAddModule = (moduleId) => {
    const m = modules.find(m => m.module_id === Number(moduleId));
    if (m && !selectedModules.find(sm => sm.module_id === m.module_id)) {
      setSelectedModules([...selectedModules, { ...m, teachingHours: 0 }]);
    }
  };

  const handleRemoveModule = (moduleId) =>
    setSelectedModules(selectedModules.filter(sm => sm.module_id !== moduleId));

  const handleModuleTeachingHoursChange = (moduleId, hoursValue) => {
    const numeric = parseFloat(hoursValue);
    const safe = Number.isNaN(numeric) ? 0 : clampTeachingHours(numeric);
    setSelectedModules(selectedModules.map(sm =>
      sm.module_id === moduleId ? { ...sm, teachingHours: safe } : sm
    ));
  };

  // Transform for backend: use selected LOTS/HOTS order and let backend randomize Bloom level.
  const transformQuestionConfigsForBackend = (configs) => {
    return configs.map(c => {
      const resolvedDifficulty = c.difficulty === 'hots' ? 'hard' : 'easy';
      return {
      type: c.type,
      count: c.count,
      points: c.points,
      bloom_level: 'random',
      description: (c.description || '').trim(),
      difficulty_distribution: {
        easy:   resolvedDifficulty === 'easy'   ? c.count : 0,
        medium: 0,
        hard:   resolvedDifficulty === 'hard'   ? c.count : 0,
      },
      };
    });
  };

  const onGenerateSubmit = async (data) => {
    if (!currentUser) return;

    if (data.duration_minutes > 150) { toast.error('Duration cannot exceed 150 minutes'); return; }
    if (data.passing_score    > 100) { toast.error('Passing score cannot exceed 100%');   return; }
    if (targetScoreLimit      > 150) { toast.error('Score limit cannot exceed 150');       return; }
    if (selectedModules.length === 0){ toast.error('Please select at least one module');   return; }
    if (selectedModules.some(m => (Number(m.teachingHours) || 0) <= 0)) {
      toast.error(`Please set teaching hours for all selected modules (${TERM_COVERAGE_HINT})`); return;
    }
    if (selectedModules.some((module) => normalizeModuleStatus(module.processing_status) !== 'completed')) {
      toast.error('Wait for selected modules to finish processing, or remove the ones that failed.');
      return;
    }
    const totalQuestions = questionTypesDetails.reduce((s, c) => s + c.count, 0);
    const totalPoints    = questionTypesDetails.reduce((s, c) => s + (c.count * c.points), 0);
    const totalTime      = questionTypesDetails.reduce((s, q) => s + (q.minutes || 0), 0);

    if (totalPoints !== targetScoreLimit) {
      toast.error(`Total Points (${totalPoints}) must exactly match score limit (${targetScoreLimit}).`);
      return;
    }
    if (scoreLimitError) { toast.error('Total Score Limit must be at least 1'); return; }

    if (totalDurationMin > 0 && totalTime > totalDurationMin) {
      toast.error(`Allocated time (${totalTime} min) must not exceed exam duration (${totalDurationMin} min).`);
      return;
    }

    if (totalQuestions === 0) { toast.error('Total questions cannot be 0'); return; }

    setIsLoading(true); setGenerationProgress(1);
    if (generationTimer.current) clearInterval(generationTimer.current);
    generationTimer.current = setInterval(() => {
      setGenerationProgress(prev => prev >= 90 ? 90 : Math.min(prev + 5, 90));
    }, 400);

    try {
      const moduleCoveragePayload = selectedModules.map((sm) => ({
        module_id: sm.module_id,
        teaching_hours: toCoveragePercent(sm.teachingHours),
      }));
      const totalCoverageWeight = moduleCoveragePayload.reduce(
        (sum, module) => sum + module.teaching_hours,
        0
      );
      const payload = {
        title:            data.title,
        description:      data.description || '',
        category_id:      parseInt(data.category_id),
        duration_minutes: parseInt(data.duration_minutes),
        allocated_minutes: totalTime,
        score_limit:      targetScoreLimit,
        num_questions:    totalQuestions,
        passing_score:    parseInt(data.passing_score),
        modules:          moduleCoveragePayload,
        total_hours:      Number(totalCoverageWeight.toFixed(4)),
        module_coverage_mode: 'percent',
        module_question_targets: selectedModules.map(sm => ({
          module_id: sm.module_id,
          count: moduleQuestionTargets[sm.module_id] || 0,
        })),
        question_types_details: transformQuestionConfigsForBackend(questionTypesDetails),
        cognitive_distribution: {
          remembering: 0.30, understanding: 0.20, applying: 0.20,
          analyzing: 0.10,   evaluating: 0.10,    creating: 0.10,
        },
      };

      const createEndpoint = isDepartmentMode ? '/departments/exams' : '/exams';
      const response = await api.post(createEndpoint, payload);
      setGeneratedExam(response.data);
      setTimeout(() => previewRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 150);
      toast.success(
        isDepartmentMode
          ? 'Exam generated successfully! Save it first, then edit questions before approving.'
          : 'Exam generated successfully!'
      );
      setGenerationProgress(100);
    } catch (error) {
      const responseData = error.response?.data;
      const validationSummary = summarizeValidationErrors(responseData?.errors);
      if (validationSummary) {
        toast.error(`Please fix exam configuration: ${validationSummary}`);
      } else {
        toast.error(responseData?.message || 'Failed to generate exam');
        toast.error('Checklist: Title, Category, Duration, Passing Score, Score Limit, Question Types, Modules, and Module Hours.');
      }
      setGenerationProgress(100);
    } finally {
      if (generationTimer.current) { clearInterval(generationTimer.current); generationTimer.current = null; }
      setIsLoading(false);
      setTimeout(() => setGenerationProgress(0), 600);
    }
  };

  const onGenerateInvalid = (formErrors) => {
    const missing = [];
    if (formErrors?.title) missing.push('Exam Title');
    if (formErrors?.category_id) missing.push('Exam Category');

    if (missing.length > 0) {
      toast.error(`Please fill up required fields: ${missing.join(', ')}`);
      return;
    }

    toast.error('Please complete all required exam inputs before generating.');
  };

  const onSaveExam = async () => {
    if (!generatedExam) return;
    try {
      await api.post(`/exams/${generatedExam.exam_id}/save`, {});
      if (selectedModulesDraftKey) {
        sessionStorage.removeItem(selectedModulesDraftKey);
      }
      const successMsg = isDepartmentMode
        ? 'Exam saved. You can now edit questions before approving.'
        : 'Exam saved successfully!';
      toast.success(successMsg);
      navigate(
        isDepartmentMode
          ? `/department/review-questions/${generatedExam.exam_id}`
          : '/teacher/manage-exams'
      );
    } catch (error) {
      toast.error(error.response?.data?.message || 'Failed to save exam');
    }
  };

  const availableModules = modules.filter(m => !selectedModules.find(sm => sm.module_id === m.module_id));
  const modulesByDepartment = useMemo(() => {
    const grouped = {};

    availableModules.forEach((module) => {
      const subjectFromLookup = subjectsById.get(Number(module.subject_id));
      const subjectName = String(
        module?.subject_name || subjectFromLookup?.subject_name || 'No Subject'
      ).trim() || 'No Subject';
      const departmentName = String(
        module?.department_name || subjectFromLookup?.department_name || 'Other Department'
      ).trim() || 'Other Department';

      if (!grouped[departmentName]) grouped[departmentName] = [];
      grouped[departmentName].push({
        ...module,
        resolved_subject_name: subjectName
      });
    });

    return Object.entries(grouped).sort((a, b) => a[0].localeCompare(b[0]));
  }, [availableModules, subjectsById]);
  const saveButtonLabel = isDepartmentMode ? 'Save & Edit Questions' : 'Save Exam';
  const createExamSteps = [
    'Enter exam title, category, duration, and total score limit.',
    'Configure question types, question counts, and allocated time.',
    `Select module(s), then set teaching hours for each selected module using the ${COVERAGE_SCALE_HOURS}h term baseline.`,
    `Click Generate Exam, review the result, then click ${saveButtonLabel}.`,
  ];

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="create-exam-container">

      {/* Loading overlay */}
      {isLoading && (
        <div className="loading-overlay">
          <div className="loading-card">
            <Loader2 className="loading-spin" size={30} />
            <div>
              <div className="loading-percent">
                {uploadStatus === 'uploading' ? `${uploadProgress}%` : `${generationProgress}%`}
              </div>
              <p className="loading-caption">
                {uploadStatus === 'uploading'
                  ? `Uploading file ${currentFileIndex + 1} of ${selectedFiles.length || '?'}`
                  : 'Generating exam questions…'}
              </p>
              {showHeavyGenerationNotice && (
                <p className="loading-notice">
                  <AlertCircle size={14} className="loading-notice-icon" />
                  {HEAVY_GENERATION_MESSAGE}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Status pill */}
      <div className={`status-pill ${status.api}`}>
        <span className={`status-dot ${status.api}`} />
        {status.message}
      </div>

      <div className="exam-layout">

        {/* ════════════════════════════════════════
            LEFT — Configuration
        ════════════════════════════════════════ */}
        <Card className="config-card">
          <CardHeader>
            <CardTitle>Create Exam</CardTitle>
            <CardDescription>Configure your exam settings and question types</CardDescription>
          </CardHeader>

          <form onSubmit={handleSubmit(onGenerateSubmit, onGenerateInvalid)}>
            <CardContent className="config-content">
              <div
                style={{
                  padding: '12px 14px',
                  border: '1px solid #BFDBFE',
                  backgroundColor: '#EFF6FF',
                  borderRadius: '8px',
                  marginBottom: '16px',
                }}
              >
                <p style={{ margin: '0 0 8px 0', fontSize: '13px', fontWeight: 600, color: '#1E3A8A' }}>
                  Quick Instructions
                </p>
                <ol style={{ margin: 0, paddingLeft: '18px', fontSize: '12px', color: '#1E40AF', lineHeight: 1.5 }}>
                  {createExamSteps.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ol>
              </div>

              {/* ── Basic info ── */}
              <div className="form-group">
                <Label>Exam Title *</Label>
                <Input
                  {...register('title', { required: true })}
                  placeholder="e.g. Midterm Examination — Chapter 1–4"
                />
                {errors.title && <p className="input-error">Title is required.</p>}
              </div>

              <div className="form-group">
                <Label>Description</Label>
                <Textarea
                  {...register('description')}
                  placeholder="Optional: brief description of what this exam covers"
                  rows={2}
                />
              </div>

              <div className="form-group">
                <Label>Exam Category *</Label>
                <input
                  type="hidden"
                  {...register('category_id', { required: true, valueAsNumber: true })}
                />
                <Select onValueChange={(v) => setValue('category_id', Number(v), { shouldValidate: true })}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a category" />
                  </SelectTrigger>
                  <SelectContent>
                    {categories.map((c) => (
                      <SelectItem key={c.category_id} value={String(c.category_id)}>
                        {c.category_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.category_id && <p className="input-error">Exam category is required.</p>}
              </div>

              {/* ── Duration + Score limit ── */}
              <div className="form-row">
                <div className="form-group">
                  <Label>
                    <Clock size={12} style={{ display:'inline', marginRight:4, verticalAlign:'middle' }} />
                    Duration (minutes)
                  </Label>
                  <Input
                    type="number" placeholder="60" min={1} max={150}
                    value={durationValue}
                    {...register('duration_minutes', { valueAsNumber: true })}
                    onChange={(e) => setValue('duration_minutes', clampDuration(e.target.value))}
                  />
                  <p className="input-hint">1–150 minutes</p>
                  {durationError && <p className="input-error">Enter a duration between 1 and 150.</p>}
                </div>

                <div className="form-group">
                  <Label>
                    <Target size={12} style={{ display:'inline', marginRight:4, verticalAlign:'middle' }} />
                    Total Score Limit
                  </Label>
                  <Input
                    type="number" placeholder="50" min="1" max="150"
                    value={scoreLimitValue}
                    onChange={(e) => {
                      const n = Math.min(Math.max(parseInt(e.target.value) || 0, 0), 150);
                      setTargetScoreLimit(n <= 0 ? 0 : n);
                    }}
                  />
                  <p className="input-hint">Max total points allowed (1–150)</p>
                  {scoreLimitError && <p className="input-error">Score limit must be 1–150.</p>}
                </div>
              </div>

              {/* ── Score progress dashboard ── */}
              <div className="limits-dashboard">
                <div className="limits-header">
                  <span className="limit-label">Score Usage</span>
                  <span className="limit-value">{currentTotalPoints} / {targetScoreLimit} pts</span>
                </div>
                <div className="progress-section">
                  <div className="progress-header">
                    <span className="progress-label">Total Points Used</span>
                    <span className={`progress-value${limitErrors.pointsExceeds ? ' error' : ''}`}>
                      {currentTotalPoints} / {targetScoreLimit}
                    </span>
                  </div>
                  <Progress
                    value={Math.min((currentTotalPoints / targetScoreLimit) * 100, 100)}
                    className={limitErrors.pointsExceeds ? 'progress-bar-error' : ''}
                  />
                </div>
                <div className="feedback-message">
                  {limitErrors.pointsExceeds && (
                    <span className="feedback-error">
                      <AlertCircle className="feedback-icon" /> Total points must exactly match the score limit
                    </span>
                  )}
                  {limitErrors.timeExceeds && (
                    <span className="feedback-error">
                      <AlertCircle className="feedback-icon" /> Allocated time must not exceed exam duration
                    </span>
                  )}
                  {!limitErrors.pointsExceeds && !limitErrors.timeExceeds && currentQuestionCount > 0 && (
                    <span className="feedback-success">
                      <CheckCircle className="feedback-icon" /> Configuration looks good
                    </span>
                  )}
                  {currentQuestionCount === 0 && (
                    <span className="feedback-neutral">Add question types below to see progress</span>
                  )}
                </div>
              </div>

              {/* ── Passing score ── */}
              <div className="form-group">
                <Label>Passing Score (%)</Label>
                <Input
                  type="number" placeholder="50" min={1} max={100}
                  value={passingValue}
                  {...register('passing_score', { valueAsNumber: true })}
                  onChange={(e) => setValue('passing_score', clampPassing(e.target.value))}
                />
                <p className="input-hint">Students must score at least this % to pass (1–100)</p>
                {passingError && <p className="input-error">Enter a passing score between 1 and 100.</p>}
              </div>

              {/* ── Question type configuration ── */}
              <QuestionTypeConfigWithDifficulty
                value={questionTypesDetails}
                onChange={setQuestionTypesDetails}
                maxTotalQuestions={targetScoreLimit > 0 ? targetScoreLimit : null}
                totalDuration={totalDurationMin}
                scoreLimit={targetScoreLimit}
              />

              {/* ── Modules ── */}
              <div className="form-group">
                <Label>
                  <BookOpen size={12} style={{ display:'inline', marginRight:4, verticalAlign:'middle' }} />
                  Select Modules
                </Label>
                <Select onValueChange={handleAddModule}>
                  <SelectTrigger>
                    <SelectValue placeholder="Add a module to this exam" />
                  </SelectTrigger>
                  <SelectContent>
                    {modulesByDepartment.length === 0 ? (
                      <SelectItem value="__none__" disabled>No modules available</SelectItem>
                    ) : (
                      modulesByDepartment.map(([departmentName, mods], groupIndex) => (
                        <React.Fragment key={departmentName}>
                        <SelectGroup>
                          <SelectLabel className="bg-yellow-50 text-yellow-800 rounded-sm">{departmentName}</SelectLabel>
                          {mods.map((m) => (
                            <SelectItem key={m.module_id} value={String(m.module_id)}>
                              {m.resolved_subject_name} - {m.title} — {getModuleStatusMeta(m).shortLabel}
                            </SelectItem>
                          ))}
                        </SelectGroup>
                        {groupIndex < modulesByDepartment.length - 1 && <SelectSeparator />}
                        </React.Fragment>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>

              {selectedModules.length > 0 && (
                <div className="selected-modules">
                  <Label>{`Selected Modules & Teaching Hours (${TERM_COVERAGE_HINT})`}</Label>
                  <div className="modules-list">
                    {selectedModules.map((module) => {
                      const moduleStatus = getModuleStatusMeta(module);
                      return (
                      <div key={module.module_id} className="module-item">
                        <div className="module-title">
                          <p>
                            {module.title}
                            {module.subject_name && (
                              <span style={{ marginLeft:6, fontSize:10, fontWeight:600, color:'#4B5563', background:'#E5E7EB', borderRadius:4, padding:'1px 6px', verticalAlign:'middle' }}>
                                {module.subject_name}
                              </span>
                            )}
                          </p>
                          {moduleStatus.status !== 'completed' && (
                            <span style={{ fontSize:11, color:'#9CA3AF', marginTop:2, display:'block' }}>
                              {moduleStatus.detailLabel}
                            </span>
                          )}
                        </div>
                        <div className="module-hours">
                          <Input
                            type="number" min="0" max={String(COVERAGE_SCALE_HOURS)} step="0.1" placeholder="Hours"
                            value={module.teachingHours || ''}
                            onChange={(e) => handleModuleTeachingHoursChange(module.module_id, e.target.value)}
                            className="hours-input"
                          />
                          <div className="text-[11px] text-gray-500 mt-1">
                            {`${formatTeachingHours(module.teachingHours)}h (${formatCoveragePercent(toCoveragePercent(module.teachingHours))}%) - ${moduleQuestionTargets[module.module_id] || 0} questions`}
                          </div>
                        </div>
                        <Button
                          type="button" variant="ghost" size="sm"
                          onClick={() => handleRemoveModule(module.module_id)}
                          className="module-remove-btn"
                        >
                          <X className="remove-icon-small" />
                        </Button>
                      </div>
                      );
                    })}
                  </div>

                  <div className="hours-summary">
                    <span className="hours-required">
                      <strong>Total Coverage Weight:</strong> {formatCoveragePercent(totalCoverage)}% ({formatTeachingHours(totalCoverageHours)}h)
                    </span>
                    <span className="hours-required">
                      <strong>Reference:</strong> {COVERAGE_REFERENCE_TEXT}
                    </span>
                    {totalCoverage > 0 ? (
                      <span className="hours-required">
                        <strong>Auto Split:</strong> {currentQuestionCount} questions
                      </span>
                    ) : (
                      <span className="feedback-neutral">
                        Add module hours to enable auto split
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* ── Upload new modules ── */}
              <div className="upload-section-wrapper">
                <div className="upload-section-header">
                  <Label>Upload New Modules</Label>
                  <Button
                    type="button" variant="outline" size="sm"
                    onClick={() => setShowUploadSection(!showUploadSection)}
                    className="btn-toggle-upload"
                  >
                    {showUploadSection
                      ? <><ChevronUp size={14} style={{ marginRight:4 }} /> Hide</>
                      : <><ChevronDown size={14} style={{ marginRight:4 }} /> Show</>
                    }
                  </Button>
                </div>

                {showUploadSection && (
                  <div className="upload-section-content">
                    <div className="form-group">
                      <Label>Subject *</Label>
                      <Select onValueChange={(v) => setSelectedSubject(Number(v))} disabled={isLoading}>
                        <SelectTrigger>
                          <SelectValue placeholder="Select subject" />
                        </SelectTrigger>
                        <SelectContent>
                          {groupedSubjects.map((group, groupIndex) => (
                            <React.Fragment key={`upload-group-${group.departmentName}`}>
                              <SelectGroup>
                                <SelectLabel className="bg-yellow-50 text-yellow-800 rounded-sm">
                                  {group.departmentName}
                                </SelectLabel>
                                {group.subjects.length === 0 && (
                                  <SelectItem value={`__empty-dept-${group.key}`} disabled>
                                    No subjects yet
                                  </SelectItem>
                                )}
                                {group.subjects.map((subject) => (
                                  <SelectItem key={subject.subject_id} value={String(subject.subject_id)}>
                                    {formatSubjectLabel(subject)}
                                  </SelectItem>
                                ))}
                              </SelectGroup>
                              {groupIndex < groupedSubjects.length - 1 && <SelectSeparator />}
                            </React.Fragment>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="form-group">
                      <Label>Upload Files *</Label>
                      <label className="file-upload-area">
                        {uploadStatus === 'success'
                          ? <CheckCircle className="upload-status-icon success" />
                          : uploadStatus === 'error'
                            ? <AlertCircle className="upload-status-icon error" />
                            : <Upload className="upload-status-icon default" />}
                        <p className="upload-hint">Click or drag files here (PDF, DOC, DOCX)</p>
                        <input
                          type="file" multiple accept=".pdf,.doc,.docx"
                          className="file-input-hidden"
                          onChange={handleFileChange}
                          disabled={isLoading}
                        />
                      </label>

                      {selectedFiles.length > 0 && (
                        <div className="file-list">
                          {selectedFiles.map((file, i) => (
                            <div key={i} className={`file-item${uploadStatus === 'uploading' && i === currentFileIndex ? ' file-item-uploading' : ''}`}>
                              <FileText className="file-icon" />
                              <span className="file-name">{file.name}</span>
                              <button type="button" onClick={() => removeFile(i)} disabled={isLoading} className="file-remove-btn">
                                <X className="remove-icon" />
                              </button>
                            </div>
                          ))}
                        </div>
                      )}

                      {uploadStatus === 'uploading' && (
                        <div className="upload-progress">
                          <Progress value={uploadProgress} />
                          <p className="upload-progress-text">
                            Uploading file {currentFileIndex + 1} of {selectedFiles.length} · {uploadProgress}%
                          </p>
                        </div>
                      )}
                    </div>

                    <Button
                      type="button"
                      onClick={handleUploadModules}
                      disabled={isLoading || !selectedFiles.length || !selectedSubject}
                      className="btn-upload"
                    >
                      Upload & Add to Exam
                    </Button>
                  </div>
                )}
              </div>

            </CardContent>

            <CardFooter style={{ padding:'16px 24px', borderTop:'1px solid #E5E7EB', background:'#F9FAFB' }}>
              <Button
                type="submit"
                disabled={
                  isLoading
                }
                className="btn-generate"
              >
                {isLoading
                  ? <><Loader2 size={16} style={{ marginRight:8, animation:'spin 1s linear infinite' }} />Generating…</>
                  : ' Generate Exam'}
              </Button>
            </CardFooter>
          </form>
        </Card>

        {/* ════════════════════════════════════════
            RIGHT — Generated exam preview
        ════════════════════════════════════════ */}
        {generatedExam && (
          <Card className="results-card sticky-preview" ref={previewRef}>
            <CardHeader>
              <div className="results-header">
                <div>
                  <CardTitle>Generated Exam</CardTitle>
                  <CardDescription>
                    {isDepartmentMode
                      ? 'Review your exam, then save it to edit questions before approving'
                      : 'Review your exam before saving'}
                  </CardDescription>
                </div>
                <div className="results-actions">
                  <Button variant="outline" onClick={() => setShowTOS(!showTOS)} className="btn-toggle-tos">
                    {showTOS
                      ? 'View Questions'
                      : <><BarChart3 className="tos-icon" /> Show TOS</>}
                  </Button>
                  <Button onClick={onSaveExam} className="btn-save">
                    {saveButtonLabel}
                  </Button>
                </div>
              </div>
            </CardHeader>

            <CardContent className="results-content">
              {showTOS ? (
                <div className="tos-view">
                  <div className="stats-grid">
                    <div className="stat-card total-points">
                      <h3>Total Points</h3>
                      <p className="stat-value">{generatedExam?.tos?.total_points || 0}</p>
                    </div>
                    <div className="stat-card total-questions">
                      <h3>Total Questions</h3>
                      <p className="stat-value">{generatedExam?.tos?.total_questions || 0}</p>
                    </div>
                  </div>

                  <div className="distribution-section">
                    <h3 className="section-title">
                      <BarChart3 className="section-icon" /> Points by Question Type
                    </h3>
                    <div className="distribution-list">
                      {Object.entries(generatedExam?.tos?.points_by_question_type || {}).map(([type, pts]) => (
                        <div key={type} className="distribution-item">
                          <span className="distribution-label">{toTitleCase(type)}</span>
                          <span className="distribution-value">{pts} pts</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="distribution-section">
                    <h3 className="section-title">Cognitive Distribution</h3>
                    <div className="cognitive-grid">
                      {Object.entries(generatedExam?.tos?.cognitive_distribution || {}).map(([k, v]) => (
                        <div key={k} className="cognitive-item">
                          <span className="cognitive-label">{toTitleCase(k)}</span>
                          <span className="cognitive-value">{v} Qs</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="distribution-section">
                    <h3 className="section-title">Difficulty Distribution</h3>
                    <div className="difficulty-grid">
                      {Object.entries(generatedExam?.tos?.difficulty_distribution || {}).map(([k, v]) => (
                        <div key={k} className="difficulty-card">
                          <div className="difficulty-level">{k}</div>
                          <div className="difficulty-count">{v} Questions</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="questions-scroll custom-scrollbar">
                  <div className="questions-view">
                    {generatedExam.questions.map((q, i) => (
                      <div key={i} className="question-card">
                        <div className="question-header">
                          <div className="question-number">{i + 1}</div>
                          <div className="question-body">
                            <p className="question-text">
                              <span className="question-plain-text">{q.question_text}</span>
                            </p>
                            <span className="question-points">{q.points} pts</span>
                          </div>
                        </div>

                        {q.options && q.options.length > 0 && (
                          <div className="question-options">
                            {q.options.map((opt, idx) => {
                              const isCorrect = opt === q.correct_answer;
                              return (
                                <div key={idx} className={isCorrect ? 'choice-block correct' : 'choice-block'}>
                                  <span className="choice-letter">{String.fromCharCode(65 + idx)}</span>
                                  <span className="choice-text">{opt}</span>
                                  {isCorrect && <span className="choice-badge">✓ Correct</span>}
                                </div>
                              );
                            })}
                          </div>
                        )}

                        {(!q.options || q.options.length === 0) && q.correct_answer && (
                          <div className="question-answer">
                            <span className="answer-label">Answer: </span>
                            <span className="answer-value">{q.correct_answer}</span>
                          </div>
                        )}

                        <div className="question-meta">
                          <span className="meta-badge type">{toTitleCase(q.question_type)}</span>
                          <span className="meta-badge difficulty">{q.difficulty_level}</span>
                          <span className="meta-badge bloom">{toTitleCase(q.bloom_level || 'remembering')}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

      </div>
    </div>
  );
}

export default CreateExam;
