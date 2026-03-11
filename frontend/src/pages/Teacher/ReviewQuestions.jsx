import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Textarea } from '../../components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import { AlertCircle } from 'lucide-react'; // Icon for feedback
import api from '../../utils/api';
import QuestionImage from '../../components/QuestionImage';

const MCQ_MIN_OPTIONS = 2;
const MCQ_MAX_OPTIONS = 5;
const EXAM_STATUS_DISPLAY = {
  draft: { label: 'DRAFT', variant: 'default', className: '' },
  pending: { label: 'PENDING', variant: 'default', className: '' },
  approved: { label: 'APPROVED', variant: 'default', className: '' },
  rejected: { label: 'REJECTED', variant: 'destructive', className: '' },
  revision_required: { label: 'REVISION REQUIRED', variant: 'destructive', className: '' },
  'Re-Used': { label: 'REVISED', variant: 'outline', className: 'border-emerald-300 bg-emerald-50 text-emerald-700' },
};

function ReviewQuestions() {
  const { examId } = useParams();
  const [exam, setExam] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [editingQuestionId, setEditingQuestionId] = useState(null);
  const [feedbackModeId, setFeedbackModeId] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [feedbackForm, setFeedbackForm] = useState({});
  const [error, setError] = useState(null);
  const [userRole, setUserRole] = useState(null);
  const [examModuleIds, setExamModuleIds] = useState([]);
  const [examModules, setExamModules] = useState([]);
  const [moduleImages, setModuleImages] = useState({});
  const [imageModuleById, setImageModuleById] = useState({});
  const [isLoadingImageOptions, setIsLoadingImageOptions] = useState(false);

  const loadImagePickerData = async (examData, currentUser) => {
    const moduleIds =
      Array.isArray(examData?.module_ids) && examData.module_ids.length > 0
        ? examData.module_ids.map((id) => Number(id)).filter(Boolean)
        : (examData?.module_id ? [Number(examData.module_id)] : []);

    setExamModuleIds(moduleIds);
    if (!moduleIds.length) {
      setExamModules([]);
      setModuleImages({});
      setImageModuleById({});
      return;
    }

    setIsLoadingImageOptions(true);
    try {
      let teacherModules = [];
      if (currentUser?.user_id) {
        const modulesRes = await api.get(`/modules/teacher/${currentUser.user_id}`, {
          params: { page: 1, per_page: 200 },
        });
        teacherModules = modulesRes.data?.modules || [];
      }

      const linkedModules = moduleIds.map((moduleId) => {
        const found = teacherModules.find((m) => Number(m.module_id) === Number(moduleId));
        return found || { module_id: moduleId, title: `Module ${moduleId}` };
      });
      setExamModules(linkedModules);

      const imageResponses = await Promise.all(
        moduleIds.map((moduleId) =>
          api.get(`/modules/${moduleId}/images`)
            .then((res) => ({ moduleId, images: res.data?.images || [] }))
            .catch(() => ({ moduleId, images: [] }))
        )
      );

      const nextModuleImages = {};
      const nextImageModuleById = {};
      imageResponses.forEach(({ moduleId, images }) => {
        nextModuleImages[moduleId] = images;
        images.forEach((img) => {
          nextImageModuleById[img.image_id] = moduleId;
        });
      });

      setModuleImages(nextModuleImages);
      setImageModuleById(nextImageModuleById);
    } finally {
      setIsLoadingImageOptions(false);
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        setError(null);
        
        // Get user role
        const user = JSON.parse(localStorage.getItem('user')) || {};
        setUserRole(user.role || 'teacher');

        const res = await api.get(`/exams/${examId}`);
        
        console.log('API Response:', res.data);
        
        if (res.data.success) {
          setExam(res.data.exam);
          await loadImagePickerData(res.data.exam, user);
          
          // FIX: Questions are nested inside exam object, not at top level
          const parsedQuestions = (res.data.exam.questions || []).map(q => ({
            ...q,
            options: typeof q.options === 'string' ? JSON.parse(q.options || '[]') : (q.options || []),
            feedback: q.feedback || '',
            image_module_id: q.image_module_id || null,
          }));
          setQuestions(parsedQuestions);
        } else {
          setError('Failed to load exam data');
        }
      } catch (err) {
        console.error('Failed to load questions', err);
        setError(err.response?.data?.message || 'Failed to load questions');
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [examId]);

  const BLOOM_LEVELS_BY_DIFFICULTY = {
    easy:   ['remembering', 'understanding'],
    medium: ['applying', 'analyzing', 'problem_solving'],
    hard:   ['evaluating', 'creating', 'problem_solving'],
  };

  const startEdit = (q) => {
    const normalizedOptions = (Array.isArray(q.options) ? q.options : []).map((opt) =>
      (opt ?? '').toString()
    );
    const normalizedNonEmptyOptions = normalizedOptions
      .map((opt) => opt.trim())
      .filter(Boolean);
    const existingCorrect = (q.correct_answer ?? '').toString().trim();
    const initialCorrect =
      q.question_type === 'multiple_choice'
        ? (normalizedNonEmptyOptions.includes(existingCorrect) ? existingCorrect : '')
        : q.correct_answer;

    setEditingQuestionId(q.question_id);
    const resolvedImageModuleId =
      q.image_module_id ||
      imageModuleById[q.image_id] ||
      examModuleIds[0] ||
      null;

    setEditForm({
      question_text: q.question_text,
      question_type: q.question_type,
      difficulty_level: q.difficulty_level,
      bloom_level: q.bloom_level || q.cognitive_level || 'remembering',
      points: q.points,
      correct_answer: initialCorrect,
      options: normalizedOptions,
      image_id: q.image_id || null,
      selected_image_module_id: resolvedImageModuleId,
    });
  };

  const saveEdit = async () => {
    try {
      let payload = {
        question_text: editForm.question_text,
        question_type: editForm.question_type,
        difficulty_level: editForm.difficulty_level,
        bloom_level: editForm.bloom_level || 'remembering',
        points: Number(editForm.points) || 1,
        correct_answer: editForm.correct_answer,
        image_id: editForm.image_id ? Number(editForm.image_id) : null,
      };

      if (payload.question_type === 'multiple_choice') {
        const normalizedOptions = (editForm.options || [])
          .map((opt) => (opt || '').trim())
          .filter(Boolean);

        if (normalizedOptions.length < MCQ_MIN_OPTIONS) {
          alert(`Multiple Choice must have at least ${MCQ_MIN_OPTIONS} options.`);
          return;
        }

        if (normalizedOptions.length > MCQ_MAX_OPTIONS) {
          alert(`Multiple Choice can only have up to ${MCQ_MAX_OPTIONS} options.`);
          return;
        }

        const uniqueCount = new Set(normalizedOptions.map((opt) => opt.toLowerCase())).size;
        if (uniqueCount !== normalizedOptions.length) {
          alert('Multiple Choice options must be unique.');
          return;
        }

        const correctedAnswer = (payload.correct_answer || '').trim();
        if (!correctedAnswer) {
          alert('Please select a correct answer for Multiple Choice.');
          return;
        }
        if (!normalizedOptions.includes(correctedAnswer)) {
          alert('Correct answer must match one of the current options.');
          return;
        }

        payload = {
          ...payload,
          options: normalizedOptions,
          correct_answer: correctedAnswer,
        };
      }

      const saveRes = await api.put(`/exams/questions/${editingQuestionId}`, payload);
      const savedQuestion = saveRes?.data?.question || {};
      const savedFeedback = Object.prototype.hasOwnProperty.call(savedQuestion, 'feedback')
        ? savedQuestion.feedback
        : undefined;
      const nextExamStatus = saveRes?.data?.exam_admin_status;
      if (nextExamStatus) {
        setExam((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            admin_status: nextExamStatus,
            admin_feedback: saveRes?.data?.exam_admin_feedback ?? prev.admin_feedback,
          };
        });
      }

      if (payload.image_id && editForm.selected_image_module_id) {
        setImageModuleById((prev) => ({
          ...prev,
          [payload.image_id]: Number(editForm.selected_image_module_id),
        }));
      }
      
      setQuestions(qs =>
        qs.map(q =>
          q.question_id === editingQuestionId
              ? {
                  ...q,
                  ...payload,
                  feedback: savedFeedback !== undefined ? savedFeedback : q.feedback,
                  image_module_id: payload.image_id
                    ? (Number(editForm.selected_image_module_id) || imageModuleById[payload.image_id] || null)
                    : null,
                }
            : q
        )
      );
      setEditingQuestionId(null);
    } catch (err) {
      console.error('Save failed', err);
      alert(err.response?.data?.message || 'Failed to save question');
    }
  };

  const saveFeedback = async (questionId) => {
    try {
      await api.put(`/exams/questions/${questionId}/feedback`, {
        feedback: feedbackForm[questionId]
      });
      
      setQuestions(qs =>
        qs.map(q =>
          q.question_id === questionId
            ? { ...q, feedback: feedbackForm[questionId] }
            : q
        )
      );
      setFeedbackModeId(null);
      alert('Feedback saved successfully');
    } catch (err) {
      console.error('Feedback save failed', err);
      alert(err.response?.data?.message || 'Failed to save feedback');
    }
  };

  const deleteQuestion = async (id) => {
    if (!window.confirm('Delete this question?')) return;
    try {
      await api.delete(`/exams/questions/${id}`);
      setQuestions(qs => qs.filter(q => q.question_id !== id));
    } catch (err) {
      console.error('Delete failed', err);
      alert(err.response?.data?.message || 'Failed to delete question');
    }
  };

  const updateOption = (index, value) => {
    const newOptions = [...editForm.options];
    newOptions[index] = value;

    let newCorrect = editForm.correct_answer;

    const normalizedOptionValues = newOptions
      .map((opt) => (opt || '').trim())
      .filter(Boolean);
    const normalizedCorrect = (newCorrect || '').trim();
    if (!normalizedCorrect || !normalizedOptionValues.includes(normalizedCorrect)) {
      newCorrect = '';
    } else {
      newCorrect = normalizedCorrect;
    }

    setEditForm({ ...editForm, options: newOptions, correct_answer: newCorrect });
  };

  const addOption = () => {
    if ((editForm.options || []).length >= MCQ_MAX_OPTIONS) return;
    const nextIndex = (editForm.options || []).length + 1;
    const newValue = `Option ${nextIndex}`;
    const newOptions = [...editForm.options, newValue];
    const normalizedCorrect = (editForm.correct_answer || '').trim();
    const normalizedOptionValues = newOptions
      .map((opt) => (opt || '').trim())
      .filter(Boolean);
    const newCorrect = normalizedOptionValues.includes(normalizedCorrect)
      ? normalizedCorrect
      : '';
    setEditForm({ 
      ...editForm, 
      options: newOptions,
      correct_answer: newCorrect
    });
  };

  const removeOption = (index) => {
    const newOptions = editForm.options.filter((_, i) => i !== index);
    const normalizedCorrect = (editForm.correct_answer || '').trim();
    const normalizedOptionValues = newOptions
      .map((opt) => (opt || '').trim())
      .filter(Boolean);
    const newCorrect = normalizedOptionValues.includes(normalizedCorrect)
      ? normalizedCorrect
      : '';
    setEditForm({ ...editForm, options: newOptions, correct_answer: newCorrect });
  };

  const updateImageModule = (moduleIdValue) => {
    const selectedModuleId = Number(moduleIdValue);
    if (!selectedModuleId) {
      setEditForm({
        ...editForm,
        selected_image_module_id: null,
        image_id: null,
      });
      return;
    }

    const selectedModuleImages = moduleImages[selectedModuleId] || [];
    const keepCurrentImage = selectedModuleImages.some(
      (img) => Number(img.image_id) === Number(editForm.image_id)
    );

    setEditForm({
      ...editForm,
      selected_image_module_id: selectedModuleId,
      image_id: keepCurrentImage ? Number(editForm.image_id) : null,
    });
  };

  const updateSelectedImage = (imageValue) => {
    if (imageValue === '__none') {
      setEditForm({ ...editForm, image_id: null });
      return;
    }
    setEditForm({ ...editForm, image_id: Number(imageValue) });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-12 w-12 border-b-2 border-yellow-500 rounded-full"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-red-600 mb-4">{error}</p>
            <Link to="/teacher/manage-exams">
              <Button>Back to Exams</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          {(() => {
            const statusConfig = EXAM_STATUS_DISPLAY[exam?.admin_status] || {
              label: (exam?.admin_status || '').replace('_', ' ').toUpperCase(),
              variant: 'default',
              className: '',
            };
            return (
              <>
                <h1 className="text-2xl font-bold text-gray-900">
                  {exam?.admin_status === 'revision_required' ? 'Revise Exam' : 'Review Questions'}
                </h1>
                {/* FIX: Changed <p> to <div> to avoid nesting <div> (Badge) inside <p> */}
                <div className="text-sm text-gray-600">
                  Exam: {exam?.title} - {questions.length} questions
                  {exam?.admin_status && (
                    <Badge variant={statusConfig.variant} className={`ml-2 ${statusConfig.className}`.trim()}>
                      {statusConfig.label}
                    </Badge>
                  )}
                </div>
              </>
            );
          })()}
        </div>
        <div className="flex gap-2">
          <Link to={`/teacher/review-tos/${examId}`}>
            <Button variant="outline">View TOS</Button>
          </Link>
          <Link to={`/teacher/exam-preview/${examId}`}>
            <Button variant="outline">Preview</Button>
          </Link>
          <Link to="/teacher/manage-exams">
            <Button variant="outline">Back</Button>
          </Link>
        </div>
      </div>

      {/* NEW: General Exam Feedback Banner */}
      {exam?.admin_feedback && exam.admin_status === 'revision_required' && (
        <Card className="border-red-500 bg-red-50">
          <CardContent className="pt-6">
            <div className="flex gap-3">
              <AlertCircle className="h-6 w-6 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="font-bold text-red-900 mb-1">Department Feedback</h3>
                <p className="text-red-800 whitespace-pre-wrap">{exam.admin_feedback}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Questions */}
      {questions.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-gray-500">No questions found for this exam.</p>
            <p className="text-sm text-gray-400 mt-2">
              Questions should be automatically generated when you create an exam.
            </p>
          </CardContent>
        </Card>
      ) : (
        questions.map((q, index) => (
          <Card key={q.question_id} className={q.feedback ? "border-red-500 border-2" : ""}>
            <CardHeader>
              <div className="flex justify-between items-start">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    Question {index + 1}
                    {q.feedback && <Badge variant="destructive">Revision Required</Badge>}
                  </CardTitle>
                  <div className="flex gap-2 mt-1">
                    <Badge variant="outline">{q.question_type}</Badge>
                    <Badge>{q.difficulty_level}</Badge>
                    <Badge variant="secondary">{q.bloom_level || q.cognitive_level || 'remembering'}</Badge>
                    <Badge variant="secondary">{q.points} pts</Badge>
                  </div>
                </div>

                <div className="flex gap-2">
                  {/* Department / Admin Feedback Actions */}
                  {(userRole === 'department' || userRole === 'admin') && (
                    <>
                      {feedbackModeId === q.question_id ? (
                        <Button size="sm" onClick={() => saveFeedback(q.question_id)}>Save Feedback</Button>
                      ) : (
                        <Button size="sm" variant="outline" onClick={() => {
                          setFeedbackModeId(q.question_id);
                          setFeedbackForm({ ...feedbackForm, [q.question_id]: q.feedback || '' });
                        }}>
                          {q.feedback ? "Edit Feedback" : "Add Feedback"}
                        </Button>
                      )}
                    </>
                  )}
                  
                  {/* Edit/Delete Actions */}
                  {editingQuestionId === q.question_id ? (
                    <>
                      <Button size="sm" onClick={saveEdit}>Save</Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setEditingQuestionId(null)}
                      >
                        Cancel
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button size="sm" variant="outline" onClick={() => startEdit(q)}>
                        Edit Content
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-red-600"
                        onClick={() => deleteQuestion(q.question_id)}
                      >
                        Delete
                      </Button>
                    </>
                  )}
                </div>
              </div>
            </CardHeader>

            <CardContent>
              {/* Question Specific Feedback */}
              {(q.feedback || feedbackModeId === q.question_id) && (
                <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-md">
                  <Label className="text-red-700 font-bold mb-2 block">Question Feedback:</Label>
                  {feedbackModeId === q.question_id ? (
                    <Textarea
                      value={feedbackForm[q.question_id] || ''}
                      onChange={(e) => setFeedbackForm({ ...feedbackForm, [q.question_id]: e.target.value })}
                      placeholder="Enter specific revision instructions for this question..."
                      rows={3}
                    />
                  ) : (
                    <p className="text-red-800 whitespace-pre-wrap">{q.feedback}</p>
                  )}
                </div>
              )}

              {/* Content Edit Section */}
              {editingQuestionId === q.question_id ? (
                <div className="space-y-4">
                  {/* Question Text */}
                  <div>
                    <Label>Question</Label>
                    <Textarea
                      value={editForm.question_text}
                      onChange={e => setEditForm({ ...editForm, question_text: e.target.value })}
                      rows={3}
                    />
                  </div>

                  {/* Type, Difficulty, Points */}
                  <div className="grid md:grid-cols-3 gap-4">
                    <div>
                      <Label>Type</Label>
                      <Select value={editForm.question_type} onValueChange={v => setEditForm({ ...editForm, question_type: v })}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="multiple_choice">Multiple Choice</SelectItem>
                          <SelectItem value="true_false">True or False</SelectItem>
                          <SelectItem value="fill_in_blank">Fill in the Blanks</SelectItem>
                          <SelectItem value="identification">Identification</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label>Difficulty</Label>
                      <Select
                        value={editForm.difficulty_level}
                        onValueChange={v => {
                          const firstBloom = (BLOOM_LEVELS_BY_DIFFICULTY[v] || [])[0] || 'remembering';
                          setEditForm({ ...editForm, difficulty_level: v, bloom_level: firstBloom });
                        }}
                      >
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="easy">Easy (30%)</SelectItem>
                          <SelectItem value="medium">Moderate/Medium (50%)</SelectItem>
                          <SelectItem value="hard">Difficult/Hard (20%)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label>Bloom's Level</Label>
                      <Select value={editForm.bloom_level || 'remembering'} onValueChange={v => setEditForm({ ...editForm, bloom_level: v })}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {(BLOOM_LEVELS_BY_DIFFICULTY[editForm.difficulty_level] || []).map(level => (
                            <SelectItem key={level} value={level}>
                              {level === 'problem_solving'
                                ? 'Problem Solving'
                                : level.charAt(0).toUpperCase() + level.slice(1)}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label>Points</Label>
                      <Input type="number" value={editForm.points} onChange={e => setEditForm({ ...editForm, points: Number(e.target.value) })} />
                    </div>
                  </div>

                  {/* Options for Multiple Choice */}
                  {editForm.question_type === 'multiple_choice' && (
                    <div>
                      <Label>Options</Label>
                      <div className="space-y-2">
                        {editForm.options.map((opt, idx) => (
                          <div key={idx} className="flex gap-2">
                            <Input value={opt} onChange={e => updateOption(idx, e.target.value)} placeholder={`Option ${idx + 1}`} />
                            <Button variant="outline" size="sm" onClick={() => removeOption(idx)} disabled={editForm.options.length <= 2}>Remove</Button>
                          </div>
                        ))}
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={addOption}
                          disabled={(editForm.options || []).length >= MCQ_MAX_OPTIONS}
                        >
                          Add Option ({(editForm.options || []).length}/{MCQ_MAX_OPTIONS})
                        </Button>
                        <p className="text-xs text-gray-500">
                          Multiple Choice options are optional (minimum {MCQ_MIN_OPTIONS}, maximum {MCQ_MAX_OPTIONS}).
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Image Attachment from Module Images */}
                  <div className="space-y-2">
                    <Label>Insert Image from Module Images</Label>
                    {examModuleIds.length === 0 ? (
                      <p className="text-xs text-gray-500">
                        No linked modules found for this exam.
                      </p>
                    ) : (
                      <>
                        <div className="grid md:grid-cols-2 gap-3">
                          <div>
                            <Label className="text-xs text-gray-600">Module</Label>
                            <Select
                              value={
                                editForm.selected_image_module_id
                                  ? String(editForm.selected_image_module_id)
                                  : undefined
                              }
                              onValueChange={updateImageModule}
                            >
                              <SelectTrigger><SelectValue placeholder="Select module" /></SelectTrigger>
                              <SelectContent>
                                {examModules.map((module) => (
                                  <SelectItem key={module.module_id} value={String(module.module_id)}>
                                    {module.title || `Module ${module.module_id}`}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>

                          <div>
                            <Label className="text-xs text-gray-600">Image</Label>
                            <Select
                              value={editForm.image_id ? String(editForm.image_id) : '__none'}
                              onValueChange={updateSelectedImage}
                              disabled={!editForm.selected_image_module_id || isLoadingImageOptions}
                            >
                              <SelectTrigger><SelectValue placeholder="Select image" /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="__none">No image</SelectItem>
                                {(moduleImages[Number(editForm.selected_image_module_id)] || []).map((img) => (
                                  <SelectItem key={img.image_id} value={String(img.image_id)}>
                                    Image #{(img.image_index ?? 0) + 1} (ID: {img.image_id})
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                        </div>

                        {editForm.image_id && (
                          <div className="rounded-md border border-gray-200 p-2">
                            <QuestionImage
                              imageId={editForm.image_id}
                              moduleId={Number(editForm.selected_image_module_id) || imageModuleById[editForm.image_id]}
                              alt="Attached question image"
                            />
                          </div>
                        )}
                        <p className="text-xs text-gray-500">
                          Select a module image to attach to this question.
                        </p>
                      </>
                    )}
                  </div>

                  {/* Correct Answer */}
                  <div>
                    <Label>Correct Answer</Label>
                    {editForm.question_type === 'multiple_choice' ? (
                      <Select
                        value={editForm.correct_answer || undefined}
                        onValueChange={v => setEditForm({ ...editForm, correct_answer: v })}
                      >
                        <SelectTrigger><SelectValue placeholder="Select correct answer" /></SelectTrigger>
                        <SelectContent>
                          {(editForm.options || [])
                            .map((opt) => (opt || '').trim())
                            .filter(Boolean)
                            .map((opt, idx) => (
                              <SelectItem key={`${opt}-${idx}`} value={opt}>{opt}</SelectItem>
                            ))}
                        </SelectContent>
                      </Select>
                    ) : editForm.question_type === 'true_false' ? (
                      <Select value={editForm.correct_answer} onValueChange={v => setEditForm({ ...editForm, correct_answer: v })}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="True">True</SelectItem>
                          <SelectItem value="False">False</SelectItem>
                        </SelectContent>
                      </Select>
                    ) : (
                      <Input value={editForm.correct_answer} onChange={e => setEditForm({ ...editForm, correct_answer: e.target.value })} />
                    )}
                    {editForm.question_type === 'multiple_choice' && !(editForm.correct_answer || '').trim() && (
                      <p className="text-xs text-red-600 mt-1">
                        Please select the correct answer before saving.
                      </p>
                    )}
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-amber-900 whitespace-pre-wrap leading-relaxed tracking-normal font-sans break-words text-base">
                    {q.question_text}
                  </p>
                  {q.image_id && (q.image_module_id || imageModuleById[q.image_id]) && (
                    <QuestionImage
                      imageId={q.image_id}
                      moduleId={q.image_module_id || imageModuleById[q.image_id]}
                      alt={`Question ${index + 1} illustration`}
                    />
                  )}
                  {q.question_type === 'multiple_choice' && q.options && q.options.length > 0 && (
                    <div className="ml-4 space-y-1">
                      {q.options.map((opt, idx) => (
                        <div key={idx} className={`text-sm ${opt === q.correct_answer ? 'text-green-600 font-semibold' : 'text-gray-600'}`}>
                          {String.fromCharCode(65 + idx)}. {opt}
                          {opt === q.correct_answer && ' ✓'}
                        </div>
                      ))}
                    </div>
                  )}
                  {q.question_type !== 'multiple_choice' && (
                    <div className="text-sm">
                      <span className="font-semibold text-gray-700">Correct Answer: </span>
                      <span className="text-green-600">{q.correct_answer}</span>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        ))
      )}
    </div>
  );
}

export default ReviewQuestions;
