import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { toast } from 'react-hot-toast';
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
import QuestionImage from '../../components/QuestionImage';
import api from '../../utils/api';

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

const BLOOM_LEVELS_BY_DIFFICULTY = {
  easy: ['remembering', 'understanding'],
  medium: ['applying', 'analyzing', 'problem_solving'],
  hard: ['evaluating', 'creating', 'problem_solving'],
};

function ReviewQuestions() {
  const { examId } = useParams();
  const navigate = useNavigate();
  const [exam, setExam] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isApproving, setIsApproving] = useState(false);
  const [editingQuestionId, setEditingQuestionId] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [error, setError] = useState(null);
  const [examModuleIds, setExamModuleIds] = useState([]);
  const [examModules, setExamModules] = useState([]);
  const [moduleImages, setModuleImages] = useState({});
  const [imageModuleById, setImageModuleById] = useState({});
  const [isLoadingImageOptions, setIsLoadingImageOptions] = useState(false);

  const isApproved = (exam?.admin_status || '').toLowerCase() === 'approved';

  const loadImagePickerData = async (examData, departmentModules) => {
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
      const linkedModules = moduleIds.map((moduleId) => {
        const found = (departmentModules || []).find((module) => Number(module.module_id) === Number(moduleId));
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
        images.forEach((image) => {
          nextImageModuleById[image.image_id] = moduleId;
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

        const [previewRes, modulesRes] = await Promise.all([
          api.get(`/departments/exams/${examId}/preview`),
          api.get('/departments/modules'),
        ]);

        if (!previewRes.data?.success) {
          setError(previewRes.data?.message || 'Failed to load exam data');
          return;
        }

        const examData = previewRes.data.exam || null;
        const parsedQuestions = (previewRes.data.questions || []).map((question) => ({
          ...question,
          options: typeof question.options === 'string'
            ? JSON.parse(question.options || '[]')
            : (question.options || []),
          feedback: question.feedback || '',
          image_module_id: question.image_module_id || null,
        }));

        setExam(examData);
        setQuestions(parsedQuestions);
        await loadImagePickerData(examData, modulesRes.data?.modules || []);
      } catch (err) {
        setError(err.response?.data?.message || 'Failed to load questions');
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [examId]);

  const startEdit = (question) => {
    const normalizedOptions = (Array.isArray(question.options) ? question.options : []).map((option) =>
      (option ?? '').toString()
    );
    const normalizedNonEmptyOptions = normalizedOptions
      .map((option) => option.trim())
      .filter(Boolean);
    const existingCorrect = (question.correct_answer ?? '').toString().trim();
    const initialCorrect =
      question.question_type === 'multiple_choice'
        ? (normalizedNonEmptyOptions.includes(existingCorrect) ? existingCorrect : '')
        : question.correct_answer;

    setEditingQuestionId(question.question_id);
    const resolvedImageModuleId =
      question.image_module_id ||
      imageModuleById[question.image_id] ||
      examModuleIds[0] ||
      null;

    setEditForm({
      question_text: question.question_text,
      question_type: question.question_type,
      difficulty_level: question.difficulty_level,
      bloom_level: question.bloom_level || question.cognitive_level || 'remembering',
      points: question.points,
      correct_answer: initialCorrect,
      options: normalizedOptions,
      image_id: question.image_id || null,
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
          .map((option) => (option || '').trim())
          .filter(Boolean);

        if (normalizedOptions.length < MCQ_MIN_OPTIONS) {
          toast.error(`Multiple Choice must have at least ${MCQ_MIN_OPTIONS} options.`);
          return;
        }

        if (normalizedOptions.length > MCQ_MAX_OPTIONS) {
          toast.error(`Multiple Choice can only have up to ${MCQ_MAX_OPTIONS} options.`);
          return;
        }

        const uniqueCount = new Set(normalizedOptions.map((option) => option.toLowerCase())).size;
        if (uniqueCount !== normalizedOptions.length) {
          toast.error('Multiple Choice options must be unique.');
          return;
        }

        const correctedAnswer = (payload.correct_answer || '').trim();
        if (!correctedAnswer) {
          toast.error('Please select a correct answer for Multiple Choice.');
          return;
        }

        if (!normalizedOptions.includes(correctedAnswer)) {
          toast.error('Correct answer must match one of the current options.');
          return;
        }

        payload = {
          ...payload,
          options: normalizedOptions,
          correct_answer: correctedAnswer,
        };
      }

      const saveRes = await api.put(
        `/departments/exams/${examId}/questions/${editingQuestionId}`,
        payload
      );
      const savedQuestion = saveRes?.data?.question || {};
      const nextExamStatus = saveRes?.data?.exam_admin_status;

      if (nextExamStatus) {
        setExam((prev) => (
          prev
            ? {
                ...prev,
                admin_status: nextExamStatus,
                admin_feedback: saveRes?.data?.exam_admin_feedback ?? prev.admin_feedback,
              }
            : prev
        ));
      }

      if (payload.image_id && editForm.selected_image_module_id) {
        setImageModuleById((prev) => ({
          ...prev,
          [payload.image_id]: Number(editForm.selected_image_module_id),
        }));
      }

      setQuestions((currentQuestions) =>
        currentQuestions.map((question) =>
          question.question_id === editingQuestionId
            ? {
                ...question,
                ...payload,
                feedback: Object.prototype.hasOwnProperty.call(savedQuestion, 'feedback')
                  ? savedQuestion.feedback
                  : question.feedback,
                image_module_id: payload.image_id
                  ? (Number(editForm.selected_image_module_id) || imageModuleById[payload.image_id] || null)
                  : null,
              }
            : question
        )
      );
      setEditingQuestionId(null);
      toast.success('Question updated successfully');
    } catch (err) {
      toast.error(err.response?.data?.message || 'Failed to save question');
    }
  };

  const deleteQuestion = async (questionId) => {
    if (!window.confirm('Delete this question?')) return;

    try {
      await api.delete(`/departments/exams/${examId}/questions/${questionId}`);
      setQuestions((currentQuestions) => {
        const nextQuestions = currentQuestions.filter((question) => question.question_id !== questionId);
        setExam((prev) => (
          prev
            ? {
                ...prev,
                total_questions: nextQuestions.length,
              }
            : prev
        ));
        return nextQuestions;
      });
      toast.success('Question deleted successfully');
    } catch (err) {
      toast.error(err.response?.data?.message || 'Failed to delete question');
    }
  };

  const approveExam = async () => {
    if (questions.length === 0) {
      toast.error('Cannot approve an exam without questions.');
      return;
    }

    setIsApproving(true);
    try {
      const response = await api.put(`/departments/exams/${examId}/approve-created`);
      toast.success(response.data?.message || 'Exam approved successfully');
      navigate('/department/approved-exams');
    } catch (err) {
      toast.error(err.response?.data?.message || 'Failed to approve exam');
    } finally {
      setIsApproving(false);
    }
  };

  const updateOption = (index, value) => {
    const nextOptions = [...(editForm.options || [])];
    nextOptions[index] = value;

    let nextCorrect = editForm.correct_answer;
    const normalizedOptionValues = nextOptions
      .map((option) => (option || '').trim())
      .filter(Boolean);
    const normalizedCorrect = (nextCorrect || '').trim();

    if (!normalizedCorrect || !normalizedOptionValues.includes(normalizedCorrect)) {
      nextCorrect = '';
    } else {
      nextCorrect = normalizedCorrect;
    }

    setEditForm({ ...editForm, options: nextOptions, correct_answer: nextCorrect });
  };

  const addOption = () => {
    if ((editForm.options || []).length >= MCQ_MAX_OPTIONS) return;

    const nextIndex = (editForm.options || []).length + 1;
    const nextValue = `Option ${nextIndex}`;
    const nextOptions = [...(editForm.options || []), nextValue];
    const normalizedCorrect = (editForm.correct_answer || '').trim();
    const normalizedOptionValues = nextOptions
      .map((option) => (option || '').trim())
      .filter(Boolean);

    setEditForm({
      ...editForm,
      options: nextOptions,
      correct_answer: normalizedOptionValues.includes(normalizedCorrect) ? normalizedCorrect : '',
    });
  };

  const removeOption = (index) => {
    const nextOptions = (editForm.options || []).filter((_, optionIndex) => optionIndex !== index);
    const normalizedCorrect = (editForm.correct_answer || '').trim();
    const normalizedOptionValues = nextOptions
      .map((option) => (option || '').trim())
      .filter(Boolean);

    setEditForm({
      ...editForm,
      options: nextOptions,
      correct_answer: normalizedOptionValues.includes(normalizedCorrect) ? normalizedCorrect : '',
    });
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
      (image) => Number(image.image_id) === Number(editForm.image_id)
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
            <Link to="/department/create-exam">
              <Button>Back to Create Exam</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  const statusConfig = EXAM_STATUS_DISPLAY[exam?.admin_status] || {
    label: (exam?.admin_status || '').replace('_', ' ').toUpperCase(),
    variant: 'default',
    className: '',
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Edit Questions</h1>
          <div className="text-sm text-gray-600">
            Exam: {exam?.title} - {questions.length} questions
            {exam?.admin_status && (
              <Badge variant={statusConfig.variant} className={`ml-2 ${statusConfig.className}`.trim()}>
                {statusConfig.label}
              </Badge>
            )}
          </div>
        </div>

        <div className="flex gap-2">
          <Link to="/department/create-exam">
            <Button variant="outline">Back</Button>
          </Link>
          <Button
            onClick={approveExam}
            disabled={isApproving || isApproved || questions.length === 0}
          >
            {isApproved ? 'Approved' : (isApproving ? 'Approving...' : 'Approve Exam')}
          </Button>
        </div>
      </div>

      {questions.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-gray-500">No questions found for this exam.</p>
            <p className="text-sm text-gray-400 mt-2">
              Add questions first before approving this exam.
            </p>
          </CardContent>
        </Card>
      ) : (
        questions.map((question, index) => (
          <Card key={question.question_id}>
            <CardHeader>
              <div className="flex justify-between items-start">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    Question {index + 1}
                  </CardTitle>
                  <div className="flex gap-2 mt-1">
                    <Badge variant="outline">{question.question_type}</Badge>
                    <Badge>{question.difficulty_level}</Badge>
                    <Badge variant="secondary">
                      {question.bloom_level || question.cognitive_level || 'remembering'}
                    </Badge>
                    <Badge variant="secondary">{question.points} pts</Badge>
                  </div>
                </div>

                <div className="flex gap-2">
                  {editingQuestionId === question.question_id ? (
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
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => startEdit(question)}
                        disabled={isApproved}
                      >
                        Edit Content
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-red-600"
                        onClick={() => deleteQuestion(question.question_id)}
                        disabled={isApproved}
                      >
                        Delete
                      </Button>
                    </>
                  )}
                </div>
              </div>
            </CardHeader>

            <CardContent>
              {editingQuestionId === question.question_id ? (
                <div className="space-y-4">
                  <div>
                    <Label>Question</Label>
                    <Textarea
                      value={editForm.question_text}
                      onChange={(e) => setEditForm({ ...editForm, question_text: e.target.value })}
                      rows={3}
                    />
                  </div>

                  <div className="grid md:grid-cols-3 gap-4">
                    <div>
                      <Label>Type</Label>
                      <Select
                        value={editForm.question_type}
                        onValueChange={(value) => setEditForm({ ...editForm, question_type: value })}
                      >
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
                        onValueChange={(value) => {
                          const firstBloom = (BLOOM_LEVELS_BY_DIFFICULTY[value] || [])[0] || 'remembering';
                          setEditForm({
                            ...editForm,
                            difficulty_level: value,
                            bloom_level: firstBloom,
                          });
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
                      <Select
                        value={editForm.bloom_level || 'remembering'}
                        onValueChange={(value) => setEditForm({ ...editForm, bloom_level: value })}
                      >
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {(BLOOM_LEVELS_BY_DIFFICULTY[editForm.difficulty_level] || []).map((level) => (
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
                      <Input
                        type="number"
                        value={editForm.points}
                        onChange={(e) => setEditForm({ ...editForm, points: Number(e.target.value) })}
                      />
                    </div>
                  </div>

                  {editForm.question_type === 'multiple_choice' && (
                    <div>
                      <Label>Options</Label>
                      <div className="space-y-2">
                        {(editForm.options || []).map((option, optionIndex) => (
                          <div key={`${optionIndex}-${option}`} className="flex gap-2">
                            <Input
                              value={option}
                              onChange={(e) => updateOption(optionIndex, e.target.value)}
                              placeholder={`Option ${optionIndex + 1}`}
                            />
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => removeOption(optionIndex)}
                              disabled={(editForm.options || []).length <= MCQ_MIN_OPTIONS}
                            >
                              Remove
                            </Button>
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
                      </div>
                    </div>
                  )}

                  <div className="space-y-2">
                    <Label>Insert Image from Module Images</Label>
                    {examModuleIds.length === 0 ? (
                      <p className="text-xs text-gray-500">No linked modules found for this exam.</p>
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
                                {(moduleImages[Number(editForm.selected_image_module_id)] || []).map((image) => (
                                  <SelectItem key={image.image_id} value={String(image.image_id)}>
                                    Image #{(image.image_index ?? 0) + 1} (ID: {image.image_id})
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
                      </>
                    )}
                  </div>

                  <div>
                    <Label>Correct Answer</Label>
                    {editForm.question_type === 'multiple_choice' ? (
                      <Select
                        value={editForm.correct_answer || undefined}
                        onValueChange={(value) => setEditForm({ ...editForm, correct_answer: value })}
                      >
                        <SelectTrigger><SelectValue placeholder="Select correct answer" /></SelectTrigger>
                        <SelectContent>
                          {(editForm.options || [])
                            .map((option) => (option || '').trim())
                            .filter(Boolean)
                            .map((option, optionIndex) => (
                              <SelectItem key={`${option}-${optionIndex}`} value={option}>
                                {option}
                              </SelectItem>
                            ))}
                        </SelectContent>
                      </Select>
                    ) : editForm.question_type === 'true_false' ? (
                      <Select
                        value={editForm.correct_answer}
                        onValueChange={(value) => setEditForm({ ...editForm, correct_answer: value })}
                      >
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="True">True</SelectItem>
                          <SelectItem value="False">False</SelectItem>
                        </SelectContent>
                      </Select>
                    ) : (
                      <Input
                        value={editForm.correct_answer}
                        onChange={(e) => setEditForm({ ...editForm, correct_answer: e.target.value })}
                      />
                    )}
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-amber-900 whitespace-pre-wrap leading-relaxed tracking-normal font-sans break-words text-base">
                    {question.question_text}
                  </p>
                  {question.image_id && (question.image_module_id || imageModuleById[question.image_id]) && (
                    <QuestionImage
                      imageId={question.image_id}
                      moduleId={question.image_module_id || imageModuleById[question.image_id]}
                      alt={`Question ${index + 1} illustration`}
                    />
                  )}
                  {question.question_type === 'multiple_choice' && question.options && question.options.length > 0 && (
                    <div className="ml-4 space-y-1">
                      {question.options.map((option, optionIndex) => (
                        <div
                          key={`${optionIndex}-${option}`}
                          className={`text-sm ${option === question.correct_answer ? 'text-green-600 font-semibold' : 'text-gray-600'}`}
                        >
                          {String.fromCharCode(65 + optionIndex)}. {option}
                          {option === question.correct_answer && ' ✓'}
                        </div>
                      ))}
                    </div>
                  )}
                  {question.question_type !== 'multiple_choice' && (
                    <div className="text-sm">
                      <span className="font-semibold text-gray-700">Correct Answer: </span>
                      <span className="text-green-600">{question.correct_answer}</span>
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
