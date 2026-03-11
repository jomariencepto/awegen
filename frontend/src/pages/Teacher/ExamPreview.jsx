import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { ArrowLeft, Loader2, Eye } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import api from '../../utils/api';
import MathText from '../../components/MathText';
import QuestionImage from '../../components/QuestionImage';

function ExamPreview() {
  const { examId } = useParams();
  const [exam, setExam] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchExamPreview = async () => {
      try {
        const response = await api.get(`/exams/preview/${examId}`);
        setExam(response.data.exam);
        setQuestions(response.data.questions || []);
      } catch (error) {
        console.error('Error fetching exam preview:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchExamPreview();
  }, [examId]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <Loader2 className="h-12 w-12 animate-spin text-yellow-500 mx-auto mb-4" />
          <p className="text-gray-600 font-medium">Loading exam preview...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-yellow-50 rounded-lg">
            <Eye className="h-6 w-6 text-yellow-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Exam Preview</h1>
            <p className="text-sm text-gray-600 mt-0.5">
              {exam?.title} • {questions.length} question{questions.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>

        <Link to="/teacher/manage-exams">
          <Button
            variant="outline"
            size="sm"
            className="border-gray-300 hover:border-yellow-500 hover:text-yellow-700"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
        </Link>
      </div>

      {/* Exam Card */}
      <Card className="bg-white shadow-sm border border-gray-200 rounded-lg">
        <CardHeader>
          <div className="flex flex-col md:flex-row md:justify-between gap-4">
            <div className="flex-1">
              <CardTitle className="text-xl font-bold text-gray-900">
                {exam?.title}
              </CardTitle>
              <p className="text-gray-600 mt-2 leading-relaxed">
                {exam?.description}
              </p>
            </div>

            <div className="bg-gray-50 rounded-lg p-4 md:min-w-[200px]">
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">Duration:</span>
                  <span className="font-semibold text-gray-900">
                    {exam?.duration_minutes} min
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Passing:</span>
                  <span className="font-semibold text-gray-900">
                    {exam?.passing_score}%
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Questions:</span>
                  <span className="font-semibold text-gray-900">
                    {questions.length}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </CardHeader>

        <CardContent className="space-y-8">
          {/* Student Info */}
          <div className="border-t border-b border-gray-200 py-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
              <div>
                <span className="font-medium text-gray-700">Name:</span>
                <span className="ml-2 border-b border-gray-400 inline-block w-48">
                  ____________________
                </span>
              </div>
              <div>
                <span className="font-medium text-gray-700">Date:</span>
                <span className="ml-2 border-b border-gray-400 inline-block w-48">
                  ____________________
                </span>
              </div>
              <div>
                <span className="font-medium text-gray-700">Course/Section:</span>
                <span className="ml-2 border-b border-gray-400 inline-block w-48">
                  ____________________
                </span>
              </div>
              <div>
                <span className="font-medium text-gray-700">Score:</span>
                <span className="ml-2 border-b border-gray-400 inline-block w-48">
                  ____________________
                </span>
              </div>
            </div>
          </div>

          {/* Questions */}
          <div className="space-y-6">
            {questions.map((question, index) => (
              <div
                key={question.question_id}
                className="border-l-2 border-gray-200 pl-4 hover:border-yellow-400 transition-colors"
              >
                <div className="flex items-start gap-3">
                  <span className="font-bold text-gray-700 min-w-[2rem]">
                    {index + 1}.
                  </span>

                  <div className="flex-1">
                    <p className="mb-3 text-gray-900 font-medium leading-relaxed">
                      <MathText text={question.question_text} />
                    </p>
                    {question.image_id && (
                      <QuestionImage
                        imageId={question.image_id}
                        moduleId={question.image_module_id}
                      />
                    )}

                    {question.question_type === 'Multiple Choice' && (
                      <div className="ml-6 space-y-2">
                        {question.options?.map((option, idx) => (
                          <div key={idx}>
                            {String.fromCharCode(65 + idx)}. {option}
                          </div>
                        ))}
                      </div>
                    )}

                    {question.question_type === 'True or False' && (
                      <div className="ml-6 flex gap-6">
                        <span>□ True</span>
                        <span>□ False</span>
                      </div>
                    )}

                    {question.question_type === 'Fill in the Blanks' && (
                      <div className="ml-6 border-b border-gray-400 w-48" />
                    )}

                    {question.question_type === 'Matching Type' && (
                      <div className="ml-6 grid grid-cols-2 gap-4">
                        <div>
                          <p className="font-medium mb-2">Column A</p>
                          {question.column_a?.map((item, idx) => (
                            <div key={idx}>
                              {idx + 1}. {item} _____
                            </div>
                          ))}
                        </div>
                        <div>
                          <p className="font-medium mb-2">Column B</p>
                          {question.column_b?.map((item, idx) => (
                            <div key={idx}>
                              {String.fromCharCode(65 + idx)}. {item}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {question.question_type === 'Problem Solving' && (
                      <div className="ml-6 space-y-3">
                        <div className="space-y-1 text-sm text-gray-500">
                          <p>Answer / Solution:</p>
                          <div className="border-b border-gray-400 w-full mt-4" />
                          <div className="border-b border-gray-400 w-full mt-4" />
                          <div className="border-b border-gray-400 w-full mt-4" />
                        </div>
                        {question.correct_answer && (
                          <details className="mt-2 bg-green-50 border border-green-200 rounded-lg p-3">
                            <summary className="text-xs font-semibold text-green-700 cursor-pointer select-none">
                              Answer Key / Solution Steps
                            </summary>
                            <div className="mt-2 text-sm text-gray-800 whitespace-pre-wrap">
                              <MathText text={question.correct_answer} />
                            </div>
                          </details>
                        )}
                      </div>
                    )}

                    <div className="mt-3 flex gap-2">
                      <Badge variant="outline" className="text-xs">
                        {question.question_type}
                      </Badge>
                      <Badge className="text-xs bg-yellow-100 text-yellow-800">
                        {question.points} {question.points === 1 ? 'pt' : 'pts'}
                      </Badge>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="text-center py-6 border-t-2 border-gray-300">
            <p className="text-lg font-semibold text-gray-700">
              — End of Examination —
            </p>
            <p className="text-sm text-gray-500 mt-2">
              Please review your answers before submitting.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default ExamPreview;
