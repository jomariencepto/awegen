import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { toast } from 'react-hot-toast';
import api from '../../utils/api';
import MathText from '../../components/MathText';
import QuestionImage from '../../components/QuestionImage';

function DepartmentExamPreview() {
  const { examId } = useParams();
  const navigate = useNavigate();

  const [exam, setExam] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [tosData, setTosData] = useState(null);
  const [activeTab, setActiveTab] = useState('questions');
  const [isLoading, setIsLoading] = useState(true);
  const [tosLoading, setTosLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (examId) {
      fetchExamPreview();
    }
  }, [examId]);

  const fetchExamPreview = async () => {
    setIsLoading(true);
    setError(null);
    try {
      console.log(`[Department] Fetching exam preview for exam_id: ${examId}`);
      // CRITICAL: Use department-specific endpoint
      const response = await api.get(`/departments/exams/${examId}/preview`);

      if (response.data.success) {
        console.log('[Department] Exam preview loaded successfully:', response.data);
        setExam(response.data.exam);

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
      } else {
        setError(response.data.message || 'Failed to load exam');
        toast.error(response.data.message || 'Failed to load exam');
      }
    } catch (err) {
      console.error('[Department] Error fetching exam preview:', err);
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
      console.log(`[Department] Fetching TOS for exam_id: ${examId}`);
      // CRITICAL: Use department-specific endpoint
      const response = await api.get(`/departments/exams/${examId}/tos`);
      if (response.data.success) {
        console.log('[Department] TOS loaded successfully:', response.data);
        setTosData(response.data);
      } else {
        toast.error(response.data.message || 'Failed to load TOS');
      }
    } catch (err) {
      console.error('[Department] Error fetching TOS:', err);
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
      </div>

      {/* Questions Tab */}
      {activeTab === 'questions' && (
        <div className="space-y-4">
          {questions.length === 0 ? (
            <Card>
              <CardContent className="pt-6 text-center py-12">
                <div className="text-gray-400 text-5xl mb-4">📝</div>
                <h3 className="text-lg font-medium text-gray-900 mb-1">No questions found</h3>
                <p className="text-gray-500">This exam doesn't have any questions yet.</p>
              </CardContent>
            </Card>
          ) : (
            questions.map((question, index) => (
              <Card key={question.question_id} className="hover:shadow-sm transition-shadow">
                <CardContent className="pt-6">
                  {/* Question Header */}
                  <div className="flex items-start gap-3 mb-4">
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 text-blue-700 font-semibold flex items-center justify-center text-sm">
                      {index + 1}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-base font-medium text-gray-900 leading-relaxed">
                          <MathText text={question.question_text} />
                        </p>
                        {question.image_id && (
                          <QuestionImage
                            imageId={question.image_id}
                            moduleId={question.image_module_id}
                          />
                        )}
                        <div className="flex-shrink-0 flex items-center gap-2">
                          <Badge variant="outline" className="text-[10px] h-5 px-1.5">
                            {question.points || 1} {question.points === 1 ? 'pt' : 'pts'}
                          </Badge>
                        </div>
                      </div>
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
                        const isCorrect = question.correct_answer === String.fromCharCode(65 + optIdx);
                        return (
                          <div
                            key={optIdx}
                            className={`flex items-start gap-2 p-2.5 rounded-md text-sm transition-colors ${
                              isCorrect
                                ? 'bg-green-50 border border-green-300'
                                : 'bg-gray-50 border border-gray-200'
                            }`}
                          >
                            <span className="font-medium text-gray-600">{String.fromCharCode(65 + optIdx)}.</span>
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

                  {/* Problem Solving: answer key with MathText + whitespace-pre-wrap for solution steps */}
                  {(question.question_type === 'problem_solving' || question.question_type === 'Problem Solving') && question.correct_answer && (
                    <div className="ml-11 mt-2">
                      <details className="bg-green-50 border border-green-200 rounded-lg p-3" open>
                        <summary className="text-xs font-semibold text-green-700 cursor-pointer select-none">
                          Answer Key / Solution Steps
                        </summary>
                        <div className="mt-2 text-sm text-gray-800 whitespace-pre-wrap">
                          <MathText text={question.correct_answer} />
                        </div>
                      </details>
                    </div>
                  )}

                  {/* Non-MCQ correct answer (non-problem-solving types) */}
                  {question.question_type !== 'multiple_choice'
                    && question.question_type !== 'problem_solving'
                    && question.question_type !== 'Problem Solving'
                    && question.correct_answer && (
                    <div className="ml-11 mt-2">
                      <p className="text-xs font-semibold text-gray-600 mb-1">Correct Answer:</p>
                      <div className="text-xs p-2 rounded bg-green-50 border border-green-300 text-green-800">
                        {question.correct_answer}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))
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
    </div>
  );
}

export default DepartmentExamPreview;