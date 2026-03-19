import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { toast } from 'react-hot-toast';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { AlertTriangle, MessageSquare, CheckCircle2 } from 'lucide-react';
import api from '../../utils/api';
import QuestionImage from '../../components/QuestionImage';

const isReviewLocked = (status) => (
  ['approved', 'rejected', 'revision_required'].includes(String(status || '').toLowerCase())
);

function ExamReview() {
  const { examId } = useParams();
  const navigate = useNavigate();

  const [exam, setExam] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [tosData, setTosData] = useState(null);
  const [activeTab, setActiveTab] = useState('questions');
  const [isLoading, setIsLoading] = useState(true);
  const [tosLoading, setTosLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [savingQuestionFeedback, setSavingQuestionFeedback] = useState({});
  
  // Per-question review state
  const [questionFeedback, setQuestionFeedback] = useState({});
  const [questionReviewStatus, setQuestionReviewStatus] = useState({});
  
  const [reviewData, setReviewData] = useState({
    action: '',
    feedback: '',
  });
  const [isFeedbackConfirmed, setIsFeedbackConfirmed] = useState(false);

  useEffect(() => {
    if (examId) {
      fetchExamPreview();
    }
  }, [examId]);

  const fetchExamPreview = async () => {
    setIsLoading(true);
    setError(null);
    try {
      console.log(`Fetching exam preview for exam_id: ${examId}`);
      const response = await api.get(`/departments/exams/${examId}/preview`);

        if (response.data.success) {
          console.log('Exam preview loaded successfully:', response.data);
          const examData = response.data.exam;
          setExam(examData);

          const rawQuestions = response.data.questions || [];
          const parsed = rawQuestions.map((q) => {
            if (q.options && typeof q.options === 'string') {
            try {
              q.options = JSON.parse(q.options);
            } catch {
              q.options = [];
            }
          }
          return q;
        });
        setQuestions(parsed);
        
        // Load existing feedback/status
        const initialFeedback = {};
        const initialStatus = {};
        parsed.forEach(q => {
          const existing = (q.feedback || '').trim();
          initialFeedback[q.question_id] = existing;
          initialStatus[q.question_id] = existing ? 'revision_required' : 'correct';
        });
        setQuestionFeedback(initialFeedback);
        setQuestionReviewStatus(initialStatus);
      } else {
        setError(response.data.message || 'Failed to load exam');
        toast.error(response.data.message || 'Failed to load exam');
      }
    } catch (err) {
      console.error('Error fetching exam preview:', err);
      const msg = err.response?.data?.message || 'Failed to load exam preview';
      setError(msg);
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchTosData = async () => {
    if (tosData) return;
    setTosLoading(true);
    try {
      console.log(`Fetching TOS for exam_id: ${examId}`);
      const response = await api.get(`/departments/exams/${examId}/tos`);
      if (response.data.success) {
        console.log('TOS loaded successfully:', response.data);
        setTosData(response.data);
      } else {
        toast.error(response.data.message || 'Failed to load TOS');
      }
    } catch (err) {
      console.error('Error fetching TOS:', err);
      toast.error(err.response?.data?.message || 'Failed to load TOS');
    } finally {
      setTosLoading(false);
    }
  };

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    if (tab === 'tos') {
      fetchTosData();
    }
  };

  const handleQuestionFeedbackChange = (questionId, value) => {
    setQuestionFeedback(prev => ({ ...prev, [questionId]: value }));
    setQuestionReviewStatus(prev => ({
      ...prev,
      [questionId]: value.trim() ? 'revision_required' : 'correct'
    }));
  };

  const handleConfirmQuestionFeedback = async (questionId) => {
    const feedbackLocked = isReviewLocked(exam?.admin_status);
    if (feedbackLocked || isSubmitting) return;

    const feedbackValue = (questionFeedback[questionId] || '').trim();
    setSavingQuestionFeedback(prev => ({ ...prev, [questionId]: true }));

    try {
      const response = await api.put(
        `/departments/exams/${examId}/questions/${questionId}/feedback`,
        { feedback: feedbackValue }
      );

      if (response.data?.success) {
        setQuestionReviewStatus(prev => ({
          ...prev,
          [questionId]: feedbackValue ? 'revision_required' : 'correct',
        }));
        setQuestions(prev => prev.map((q) => (
          q.question_id === questionId ? { ...q, feedback: feedbackValue || null } : q
        )));
        toast.success(feedbackValue ? 'Feedback saved for this question.' : 'Question confirmed.');
      } else {
        toast.error(response.data?.message || 'Failed to save feedback');
      }
    } catch (err) {
      toast.error(err.response?.data?.message || 'Failed to save feedback');
    } finally {
      setSavingQuestionFeedback(prev => ({ ...prev, [questionId]: false }));
    }
  };

  const buildQuestionReviews = () => {
    return questions.map((q) => {
      const feedback = (questionFeedback[q.question_id] || '').trim();
      const status = (questionReviewStatus[q.question_id] || '').toLowerCase();
      const isCorrect = status === 'correct' && !feedback;
      return {
        question_id: q.question_id,
        status: isCorrect ? 'correct' : 'revision_required',
        feedback: isCorrect ? '' : feedback,
      };
    });
  };

  const handleReviewSubmit = async (action) => {
    const feedbackLocked = isReviewLocked(exam?.admin_status);
    if (feedbackLocked) {
      toast.error('Review already submitted for this exam. Feedback can only be sent once.');
      return;
    }

    const questionReviews = buildQuestionReviews();
    const flaggedCount = questionReviews.filter((row) => row.status === 'revision_required').length;
    
    if (action === 'approve' && flaggedCount > 0) {
      toast.error(`Cannot approve: ${flaggedCount} question(s) flagged for revision`);
      return;
    }

    if (action === 'revision_required' && flaggedCount === 0) {
      toast.error('Add feedback to at least one question before sending to teacher.');
      return;
    }

    if (reviewData.feedback.trim() && !isFeedbackConfirmed) {
      toast.error('Please click Confirm Feedback before submitting your review action.');
      return;
    }
    
    // Overall feedback is now optional for all actions

    setIsSubmitting(true);
    try {
      const payload = {
        action,
        feedback: reviewData.feedback,
      };

      if (action === 'revision_required') {
        payload.question_reviews = questionReviews;
      }

      console.log(`Submitting review for exam_id: ${examId}`, payload);
      const response = await api.put(`/departments/exams/${examId}/approve`, payload);

      if (response.data.success) {
        if (response.data.exam) {
          setExam(response.data.exam);
        }
        toast.success(`Exam ${action === 'approve' ? 'approved' : action === 'reject' ? 'rejected' : 'sent for revision'} successfully!`);
        setTimeout(() => navigate('/department/dashboard'), 1500);
      } else {
        toast.error(response.data.message || 'Failed to submit review');
      }
    } catch (err) {
      console.error('Error submitting review:', err);
      toast.error(err.response?.data?.message || 'Failed to submit review');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto" />
          <p className="mt-4 text-gray-600">Loading exam preview...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-3xl mx-auto p-6">
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6 text-center">
            <div className="text-red-400 text-5xl mb-4">⚠️</div>
            <h3 className="text-lg font-medium text-red-800 mb-2">Failed to load exam</h3>
            <p className="text-sm text-red-600 mb-4">{error}</p>
            <div className="flex gap-3 justify-center">
              <Button onClick={fetchExamPreview} variant="outline" size="sm">
                Retry
              </Button>
              <Button onClick={() => navigate(-1)} variant="outline" size="sm">
                Go Back
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!exam) return null;

  const cogLevels = ['remembering', 'understanding', 'applying', 'analyzing', 'evaluating', 'creating'];
  const cogLabels = ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create'];
  
  const feedbackLocked = isReviewLocked(exam?.admin_status);
  const flaggedQuestions = questions.filter((q) => {
    const feedback = (questionFeedback[q.question_id] || '').trim();
    const status = (questionReviewStatus[q.question_id] || '').toLowerCase();
    return status !== 'correct' && !!feedback;
  }).length;
  const approvedQuestions = Math.max(questions.length - flaggedQuestions, 0);

  return (
    <div className="space-y-6 max-w-5xl mx-auto p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Button variant="ghost" size="sm" onClick={() => navigate(-1)} className="mb-2 -ml-2 text-gray-500">
            ← Back
          </Button>
          <h1 className="text-2xl font-bold text-gray-900">{exam.title}</h1>
          <p className="mt-1 text-sm text-gray-600">{exam.description || 'No description'}</p>
        </div>
        <Badge className="text-sm px-3 py-1" variant={exam.admin_status === 'approved' ? 'default' : 'secondary'}>
          {exam.admin_status || 'Draft'}
        </Badge>
      </div>

      {/* Flagged Questions Warning */}
      {flaggedQuestions > 0 && (
        <div className="bg-red-50 border-2 border-red-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-red-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="font-semibold text-red-900">
                {flaggedQuestions} Question{flaggedQuestions !== 1 ? 's' : ''} Flagged for Revision
              </p>
              <p className="text-sm text-red-700 mt-1">
                Review flagged questions below and ensure all feedback is saved before taking action.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Exam Info */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap gap-4">
            <div className="flex items-center gap-2 text-sm text-gray-600 bg-gray-50 px-3 py-2 rounded-lg border">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span><strong>Duration:</strong> {exam.duration_minutes || 0} mins</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-600 bg-gray-50 px-3 py-2 rounded-lg border">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span><strong>Passing:</strong> {exam.passing_score || 0}%</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-600 bg-gray-50 px-3 py-2 rounded-lg border">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span><strong>Questions:</strong> {questions.length}</span>
            </div>
            {exam.teacher_name && (
              <div className="flex items-center gap-2 text-sm text-gray-600 bg-gray-50 px-3 py-2 rounded-lg border">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
                <span><strong>Teacher:</strong> {exam.teacher_name}</span>
              </div>
            )}
            {/* Flagged Questions Counter */}
            {flaggedQuestions > 0 && (
              <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg border border-red-200">
                <AlertTriangle className="w-4 h-4" />
                <span><strong>Flagged:</strong> {flaggedQuestions}</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200">
        <button
          onClick={() => handleTabChange('questions')}
          className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 ${
            activeTab === 'questions'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          Questions ({questions.length})
          {flaggedQuestions > 0 && (
            <Badge variant="outline" className="ml-2 bg-red-50 text-red-700 border-red-300 text-[10px]">
              {flaggedQuestions} flagged
            </Badge>
          )}
        </button>
        <button
          onClick={() => handleTabChange('tos')}
          className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 ${
            activeTab === 'tos'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          TOS Report
        </button>
        <button
          onClick={() => handleTabChange('review')}
          className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 ${
            activeTab === 'review'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          Review & Approve
        </button>
      </div>

      {/* Questions Tab */}
      {activeTab === 'questions' && (
        <div className="space-y-4">
          {feedbackLocked && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
              <p className="text-sm text-amber-800">
                Feedback was already submitted for this review cycle and is now locked.
              </p>
            </div>
          )}
          {questions.length === 0 ? (
            <Card>
              <CardContent className="pt-6 text-center py-12">
                <div className="text-gray-400 text-5xl mb-4">📝</div>
                <h3 className="text-lg font-medium text-gray-900 mb-1">No questions found</h3>
                <p className="text-gray-500">This exam doesn't have any questions yet.</p>
              </CardContent>
            </Card>
          ) : (
            questions.map((question, index) => {
              const hasFeedback = questionFeedback[question.question_id]?.trim();
              const reviewStatus = (questionReviewStatus[question.question_id] || '').toLowerCase();
              const isMarkedCorrect = reviewStatus === 'correct' && !hasFeedback;
              const isSavingQuestionFeedback = !!savingQuestionFeedback[question.question_id];
              
              return (
                <Card 
                  key={question.question_id} 
                  className={`transition-all ${
                    hasFeedback 
                      ? 'border-red-300 bg-red-50 shadow-md hover:shadow-lg' 
                      : 'hover:shadow-sm'
                  }`}
                >
                  <CardContent className="pt-6">
                    {/* Question Header */}
                    <div className="flex items-start gap-3 mb-4">
                      <div className={`flex-shrink-0 w-8 h-8 rounded-full font-semibold flex items-center justify-center text-sm ${
                        hasFeedback 
                          ? 'bg-red-100 text-red-700' 
                          : 'bg-blue-100 text-blue-700'
                      }`}>
                        {index + 1}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-start justify-between gap-3">
                          <p className="text-base font-medium text-gray-900 leading-relaxed">
                            {question.question_text}
                          </p>
                          <div className="flex-shrink-0 flex items-center gap-2">
                            <Badge variant="outline" className="text-[10px] h-5 px-1.5">
                              {question.points || 1} {question.points === 1 ? 'pt' : 'pts'}
                            </Badge>
                            {hasFeedback && (
                              <Badge className="text-[10px] h-5 px-1.5 bg-red-100 text-red-700 border-red-300">
                                ⚠ Needs Revision
                              </Badge>
                            )}
                            {isMarkedCorrect && (
                              <Badge className="text-[10px] h-5 px-1.5 bg-emerald-100 text-emerald-700 border-emerald-300">
                                ✓ Correct
                              </Badge>
                            )}
                          </div>
                        </div>
                        {question.image_id && (
                          <QuestionImage
                            imageId={question.image_id}
                            moduleId={question.image_module_id}
                            alt="Attached question image"
                          />
                        )}
                        <div className="flex flex-wrap gap-2 mt-2">
                          <Badge variant="secondary" className="text-[10px] h-5 px-1.5 capitalize">
                            {question.question_type?.replace(/_/g, ' ') || 'N/A'}
                          </Badge>
                          <Badge variant="outline" className={`text-[10px] h-5 px-1.5 capitalize ${
                            question.difficulty_level === 'easy' ? 'bg-green-50 text-green-700 border-green-300' :
                            question.difficulty_level === 'medium' ? 'bg-yellow-50 text-yellow-700 border-yellow-300' :
                            'bg-gray-50 text-gray-600 border-gray-300'
                          }`}>
                            {question.difficulty_level || 'medium'}
                          </Badge>
                          <Badge variant="outline" className="text-[10px] h-5 px-1.5 capitalize bg-purple-50 text-purple-700 border-purple-300">
                            {question.cognitive_level?.replace(/_/g, ' ') || 'N/A'}
                          </Badge>
                        </div>
                      </div>
                    </div>

                    {/* MCQ Options */}
                    {question.question_type === 'multiple_choice' && question.options && question.options.length > 0 && (
                      <div className="ml-11 space-y-2 mt-3">
                        {question.options.map((option, optIdx) => {
                          // ⭐ FIXED: Check both letter (A,B,C,D) AND option text
                          const optionLetter = String.fromCharCode(65 + optIdx);
                          const isCorrect = question.correct_answer === optionLetter || 
                                          question.correct_answer === option ||
                                          question.correct_answer?.toLowerCase() === option.toLowerCase();
                          return (
                            <div
                              key={optIdx}
                              className={`flex items-start gap-2 p-2.5 rounded-md text-sm transition-colors ${
                                isCorrect
                                  ? 'bg-green-50 border border-green-300'
                                  : 'bg-gray-50 border border-gray-200'
                              }`}
                            >
                              <span className="font-medium text-gray-600">{optionLetter}.</span>
                              <span className="flex-1">{option}</span>
                              {isCorrect && (
                                <Badge variant="outline" className="bg-green-100 text-green-700 text-[9px] h-4 px-1.5 border-green-300">
                                  ✓ Correct
                                </Badge>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {/* Non-MCQ correct answer */}
                    {question.question_type !== 'multiple_choice' && question.correct_answer && (
                      <div className="ml-11 mt-2">
                        <p className="text-xs font-semibold text-gray-600 mb-1">Correct Answer:</p>
                        <div className="text-xs p-2 rounded bg-green-50 border border-green-300 text-green-800">
                          {question.correct_answer}
                        </div>
                      </div>
                    )}

                    {/* Per-Question Feedback Section */}
                    <div className={`ml-11 mt-4 p-3 rounded-lg border-2 ${
                      hasFeedback ? 'border-red-300 bg-red-50' : 'border-gray-200 bg-gray-50'
                    }`}>
                      <div className="flex items-center gap-2 mb-2">
                        <MessageSquare className={`h-4 w-4 ${hasFeedback ? 'text-red-600' : 'text-gray-600'}`} />
                        <Label htmlFor={`feedback-${question.question_id}`} className={`text-xs font-semibold ${
                          hasFeedback ? 'text-red-900' : 'text-gray-700'
                        }`}>
                          Reviewer Feedback {hasFeedback && '(Question Flagged)'}
                        </Label>
                      </div>
                      <Textarea
                        id={`feedback-${question.question_id}`}
                        placeholder="Add feedback for this question (optional)."
                        value={questionFeedback[question.question_id] || ''}
                        onChange={(e) => handleQuestionFeedbackChange(question.question_id, e.target.value)}
                        rows={2}
                        disabled={feedbackLocked || isSubmitting}
                        className={`resize-none text-xs ${
                          hasFeedback ? 'border-red-300 bg-white focus:border-red-500 focus:ring-red-500' : ''
                        }`}
                      />
                      <div className="flex gap-2 mt-2">
                        <Button
                          size="sm"
                          variant={isMarkedCorrect ? 'default' : 'outline'}
                          onClick={() => handleConfirmQuestionFeedback(question.question_id)}
                          disabled={feedbackLocked || isSubmitting || isSavingQuestionFeedback}
                          className="h-7 px-3 text-xs"
                        >
                          <CheckCircle2 className="h-3 w-3 mr-1" />
                          {isSavingQuestionFeedback
                            ? 'Saving...'
                            : hasFeedback
                              ? 'Confirm & Save'
                              : 'Confirm'}
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })
          )}
          {questions.length > 0 && (
            <Card className="border-blue-200 bg-blue-50">
              <CardContent className="pt-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-blue-900">
                      Review Summary: {flaggedQuestions} flagged, {approvedQuestions} marked correct
                    </p>
                    <p className="text-xs text-blue-800 mt-1">
                      Use the button below to send the full generated-question file feedback in one submission.
                    </p>
                  </div>
                  <Button
                    onClick={() => handleReviewSubmit('revision_required')}
                    disabled={isSubmitting || feedbackLocked || flaggedQuestions === 0}
                    className="bg-blue-600 hover:bg-blue-700"
                  >
                    {isSubmitting ? 'Sending...' : 'Add & Send Feedback'}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* TOS Tab */}
      {activeTab === 'tos' && (
        <Card>
          <CardContent className="pt-6">
            {tosLoading ? (
              <div className="flex items-center justify-center py-16">
                <div className="text-center">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto" />
                  <p className="mt-3 text-sm text-gray-500">Loading TOS...</p>
                </div>
              </div>
            ) : !tosData ? (
              <div className="text-center py-12">
                <p className="text-sm text-gray-500">No TOS data available.</p>
                <Button size="sm" variant="outline" className="mt-3" onClick={fetchTosData}>
                  Retry
                </Button>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Summary */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="bg-blue-50 rounded-lg p-3 text-center border border-blue-200">
                    <p className="text-xs text-blue-600 font-medium">Total Questions</p>
                    <p className="text-xl font-bold text-blue-800">{tosData.summary?.total_questions || questions.length}</p>
                  </div>
                  <div className="bg-green-50 rounded-lg p-3 text-center border border-green-200">
                    <p className="text-xs text-green-600 font-medium">Total Points</p>
                    <p className="text-xl font-bold text-green-800">{tosData.summary?.total_points || 0}</p>
                  </div>
                  <div className="bg-purple-50 rounded-lg p-3 text-center border border-purple-200">
                    <p className="text-xs text-purple-600 font-medium">Topics</p>
                    <p className="text-xl font-bold text-purple-800">{(tosData.matrix || []).length}</p>
                  </div>
                  <div className="bg-orange-50 rounded-lg p-3 text-center border border-orange-200">
                    <p className="text-xs text-orange-600 font-medium">Question Types</p>
                    <p className="text-xl font-bold text-orange-800">{Object.keys(tosData.question_type_distribution || {}).length}</p>
                  </div>
                </div>

                {/* TOS Matrix */}
                {(tosData.matrix || []).length > 0 && (
                  <div>
                    <h4 className="font-medium text-gray-800 mb-3">Cognitive Level Distribution by Topic</h4>
                    <div className="overflow-x-auto border rounded-lg">
                      <table className="min-w-full text-xs">
                        <thead>
                          <tr className="bg-gray-100">
                            <th className="px-3 py-2 text-left font-semibold text-gray-700 border-b border-r min-w-[140px]">Topic</th>
                            {cogLabels.map((label, i) => (
                              <th key={i} className="px-2 py-2 text-center font-semibold text-gray-700 border-b border-r">{label}</th>
                            ))}
                            <th className="px-2 py-2 text-center font-bold text-gray-800 border-b bg-gray-200">Total</th>
                          </tr>
                        </thead>
                        <tbody>
                          {tosData.matrix.map((row, idx) => (
                            <tr key={idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                              <td className="px-3 py-2 font-medium text-gray-800 border-r truncate max-w-[200px]" title={row.topic_name}>
                                {row.topic_name}
                              </td>
                              {(row.distribution || []).map((val, i) => (
                                <td key={i} className={`px-2 py-2 text-center border-r ${val > 0 ? 'text-blue-700 font-semibold bg-blue-50' : 'text-gray-400'}`}>
                                  {val}
                                </td>
                              ))}
                              <td className="px-2 py-2 text-center font-bold text-gray-800 bg-gray-100">{row.total}</td>
                            </tr>
                          ))}
                          <tr className="bg-gray-200 font-bold">
                            <td className="px-3 py-2 text-gray-800 border-r">Total</td>
                            {cogLevels.map((_, i) => {
                              const colTotal = tosData.matrix.reduce((sum, row) => sum + ((row.distribution || [])[i] || 0), 0);
                              return <td key={i} className="px-2 py-2 text-center text-gray-800 border-r">{colTotal}</td>;
                            })}
                            <td className="px-2 py-2 text-center text-gray-900 bg-gray-300">
                              {tosData.matrix.reduce((sum, row) => sum + (row.total || 0), 0)}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Difficulty Distribution */}
                {tosData.difficulty_distribution && Object.keys(tosData.difficulty_distribution).length > 0 && (
                  <div>
                    <h4 className="font-medium text-gray-800 mb-3">Difficulty Distribution</h4>
                    <div className="grid grid-cols-3 gap-3">
                      {['easy', 'medium', 'hard'].map((level) => {
                        const count = tosData.difficulty_distribution[level] || 0;
                        const total = tosData.summary?.total_questions || questions.length;
                        const pct = total > 0 ? Math.round((count / total) * 100) : 0;
                        const colors = { easy: 'green', medium: 'yellow', hard: 'red' };
                        const c = colors[level];
                        return (
                          <div key={level} className={`bg-${c}-50 border border-${c}-200 rounded-lg p-3 text-center`}>
                            <p className={`text-xs text-${c}-600 font-medium mb-1 capitalize`}>{level}</p>
                            <p className={`text-lg font-bold text-${c}-800`}>{count}</p>
                            <p className={`text-xs text-${c}-500`}>{pct}%</p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Question Type Distribution */}
                {tosData.question_type_distribution && Object.keys(tosData.question_type_distribution).length > 0 && (
                  <div>
                    <h4 className="font-medium text-gray-800 mb-3">Question Type Distribution</h4>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                      {Object.entries(tosData.question_type_distribution).map(([type, count]) => (
                        <div key={type} className="flex items-center justify-between bg-gray-50 border rounded-lg px-3 py-2">
                          <span className="text-xs font-medium text-gray-700 capitalize">{type.replace(/_/g, ' ')}</span>
                          <Badge variant="secondary" className="text-xs">{count}</Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Review & Approve Tab */}
      {activeTab === 'review' && (
        <Card>
          <CardHeader>
            <CardTitle>Review Exam</CardTitle>
            <CardDescription>
              Provide feedback and approve or request revision for this exam
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* ⭐ Warning if questions flagged */}
            {flaggedQuestions > 0 && (
              <div className="bg-red-50 border-2 border-red-200 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="h-5 w-5 text-red-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="font-semibold text-red-900 mb-1">
                      Cannot Approve: {flaggedQuestions} Question{flaggedQuestions !== 1 ? 's' : ''} Flagged
                    </p>
                    <p className="text-sm text-red-700">
                      Questions with feedback are flagged for revision. Review the Questions tab and ensure all feedback is addressed before approving this exam.
                    </p>
                  </div>
                </div>
              </div>
            )}
            
            <div className="space-y-2">
              <Label htmlFor="feedback">Overall Exam Feedback / Comments (Optional)</Label>
              <Textarea
                id="feedback"
                placeholder="Enter your overall feedback or comments about this exam... (optional)"
                value={reviewData.feedback}
                onChange={(e) => {
                  setReviewData({ ...reviewData, feedback: e.target.value });
                  setIsFeedbackConfirmed(false);
                }}
                rows={6}
                className="resize-none"
              />
              <p className="text-xs text-gray-500">
                Optional: Provide constructive feedback to help improve the exam quality. Individual question feedback can be added in the Questions tab.
              </p>
              {reviewData.feedback.trim() && (
                <div className="pt-2">
                  <Button
                    type="button"
                    variant={isFeedbackConfirmed ? 'default' : 'outline'}
                    disabled={feedbackLocked || isSubmitting}
                    onClick={() => {
                      setIsFeedbackConfirmed(true);
                      toast.success('Feedback confirmed. You can now submit your review action.');
                    }}
                  >
                    {isFeedbackConfirmed ? 'Feedback Confirmed' : 'Confirm Feedback'}
                  </Button>
                </div>
              )}
            </div>

            <div className="flex gap-3 pt-4 border-t">
              <Button
                onClick={() => handleReviewSubmit('approve')}
                disabled={isSubmitting || flaggedQuestions > 0 || feedbackLocked}
                className={`${flaggedQuestions > 0 ? 'opacity-50 cursor-not-allowed' : 'bg-green-600 hover:bg-green-700'}`}
              >
                {isSubmitting ? 'Submitting...' : (
                  <>
                    <CheckCircle2 className="h-4 w-4 mr-2" />
                    Approve Exam
                  </>
                )}
              </Button>
              <Button
                onClick={() => handleReviewSubmit('revision_required')}
                disabled={isSubmitting || feedbackLocked || flaggedQuestions === 0}
                variant="outline"
                className="border-yellow-500 text-yellow-700 hover:bg-yellow-50"
              >
                {isSubmitting ? 'Submitting...' : '↻ Request Revision'}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default ExamReview;
