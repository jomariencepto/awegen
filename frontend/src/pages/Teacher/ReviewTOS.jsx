import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Progress } from '../../components/ui/progress';
import { toast } from 'react-hot-toast';
import api from '../../utils/api';

function ReviewTOS() {
  const { examId } = useParams();
  const { currentUser } = useAuth();
  const [tosData, setTosData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchTOS = async () => {
      if (!currentUser?.user_id) {
        setIsLoading(false);
        return;
      }

      try {
        setError(null);
        const res = await api.get(`/exams/${examId}/tos`);
        
        console.log('TOS Response:', res.data); // Debug log
        
        if (res.data.success) {
          setTosData(res.data);
        } else {
          setError(res.data.message || 'Failed to load TOS data');
          toast.error(res.data.message || 'Failed to load TOS data');
        }
      } catch (error) {
        console.error('TOS fetch error:', error);
        const errorMsg = error.response?.data?.message || 'Failed to load TOS data';
        setError(errorMsg);
        toast.error(errorMsg);
      } finally {
        setIsLoading(false);
      }
    };

    fetchTOS();
  }, [examId, currentUser]);

  const handlePrint = () => {
    window.print();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-yellow-500 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading TOS...</p>
        </div>
      </div>
    );
  }

  if (error || !tosData) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <div className="text-5xl mb-4">📊</div>
          <h3 className="text-lg font-medium text-gray-900">TOS Not Available</h3>
          <p className="text-gray-500 mb-4">
            {error || 'The Table of Specification for this exam could not be found.'}
          </p>
          <Link to="/teacher/manage-exams">
            <Button>Back to Exams</Button>
          </Link>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6 print:space-y-4">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Table of Specification
          </h1>
          <p className="text-sm text-gray-600">
            Exam: {tosData.exam_title}
          </p>
        </div>

        <div className="flex gap-2">
          <Link to={`/teacher/review-questions/${examId}`}>
            <Button variant="outline">View Questions</Button>
          </Link>
          <Link to="/teacher/manage-exams">
            <Button variant="outline">Back to Exams</Button>
          </Link>
          <Button onClick={handlePrint}>
            Print TOS
          </Button>
        </div>
      </div>

      {/* Print Header (only visible when printing) */}
      <div className="hidden print:block mb-6">
        <h1 className="text-3xl font-bold text-center mb-2">
          Table of Specification
        </h1>
        <p className="text-xl text-center text-gray-700">
          {tosData.exam_title}
        </p>
      </div>

      {/* Summary */}
      <Card>
        <CardHeader>
          <CardTitle>Exam Overview</CardTitle>
        </CardHeader>
        <CardContent className="grid md:grid-cols-3 gap-4">
          <div className="text-center p-4 bg-yellow-50 rounded-lg">
            <p className="text-sm text-yellow-600 font-medium">Total Questions</p>
            <p className="text-3xl font-bold text-yellow-800">
              {tosData.total_questions || 0}
            </p>
          </div>
          <div className="text-center p-4 bg-green-50 rounded-lg">
            <p className="text-sm text-green-600 font-medium">Topics Covered</p>
            <p className="text-3xl font-bold text-green-800">
              {tosData.topics_count || 0}
            </p>
          </div>
          <div className="text-center p-4 bg-purple-50 rounded-lg">
            <p className="text-sm text-purple-600 font-medium">Cognitive Levels</p>
            <p className="text-3xl font-bold text-purple-800">
              {tosData.cognitive_levels_count || 0}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Cognitive Levels Distribution */}
      {tosData.cognitive_levels?.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Cognitive Level Distribution</CardTitle>
            <CardDescription>
              Based on Bloom's Taxonomy
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {tosData.cognitive_levels.map(level => (
              <div key={level.level}>
                <div className="flex justify-between mb-2">
                  <span className="font-medium text-gray-700">{level.level}</span>
                  <div className="text-right">
                    <span className="font-bold text-gray-900">{level.count} questions</span>
                    <span className="text-gray-500 text-sm ml-2">({level.percentage}%)</span>
                  </div>
                </div>
                <Progress value={level.percentage || 0} className="h-3" />
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Difficulty Distribution */}
      {tosData.difficulty_distribution && Object.keys(tosData.difficulty_distribution).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Difficulty Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4">
              {Object.entries(tosData.difficulty_distribution).map(([difficulty, count]) => (
                <div key={difficulty} className="text-center p-4 border rounded-lg">
                  <Badge
                    variant={
                      difficulty === 'hard'
                        ? 'destructive'
                        : difficulty === 'medium'
                        ? 'default'
                        : 'secondary'
                    }
                    className="mb-2"
                  >
                    {difficulty.charAt(0).toUpperCase() + difficulty.slice(1)}
                  </Badge>
                  <p className="text-2xl font-bold">{count}</p>
                  <p className="text-sm text-gray-500">
                    {tosData.total_questions > 0 
                      ? Math.round((count / tosData.total_questions) * 100) 
                      : 0}%
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Topic Distribution */}
      {tosData.topics?.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Topic Distribution</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-yellow-50">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">
                    Topic
                  </th>
                  <th className="px-4 py-3 text-center text-sm font-semibold text-gray-700">
                    Questions
                  </th>
                  <th className="px-4 py-3 text-center text-sm font-semibold text-gray-700">
                    Percentage
                  </th>
                  <th className="px-4 py-3 text-center text-sm font-semibold text-gray-700">
                    Difficulty
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {tosData.topics.map((topic, idx) => (
                  <tr key={topic.topic_id || idx} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-900">
                      {topic.name}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 text-center font-medium">
                      {topic.question_count || 0}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 text-center">
                      {topic.percentage || 0}%
                    </td>
                    <td className="px-4 py-3 text-center">
                      <Badge
                        variant={
                          topic.difficulty === 'hard'
                            ? 'destructive'
                            : topic.difficulty === 'medium'
                            ? 'default'
                            : 'secondary'
                        }
                      >
                        {topic.difficulty}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* Question Distribution Matrix */}
      {tosData.matrix?.length > 0 && tosData.cognitive_levels && (
        <Card>
          <CardHeader>
            <CardTitle>Topic × Cognitive Level Matrix</CardTitle>
            <CardDescription>
              Distribution of questions across topics and cognitive levels
            </CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-yellow-50">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold text-gray-700 sticky left-0 bg-yellow-50">
                    Topic
                  </th>
                  {tosData.cognitive_levels.map(level => (
                    <th key={level.level} className="px-3 py-2 text-center font-semibold text-gray-700">
                      {level.level}
                    </th>
                  ))}
                  <th className="px-3 py-2 text-center font-semibold text-gray-700 bg-yellow-100">
                    Total
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {tosData.matrix.map((row, idx) => (
                  <tr key={row.topic_id || idx} className="hover:bg-gray-50">
                    <td className="px-3 py-2 font-medium text-gray-900 sticky left-0 bg-white">
                      {row.topic_name}
                    </td>
                    {row.distribution.map((count, i) => (
                      <td key={i} className="px-3 py-2 text-center text-gray-700">
                        {count || 0}
                      </td>
                    ))}
                    <td className="px-3 py-2 text-center font-bold text-gray-900 bg-yellow-50">
                      {row.total || 0}
                    </td>
                  </tr>
                ))}
                {/* Totals Row */}
                <tr className="bg-yellow-100 font-bold">
                  <td className="px-3 py-2 text-gray-900">
                    Total
                  </td>
                  {tosData.cognitive_levels.map(level => (
                    <td key={level.level} className="px-3 py-2 text-center text-gray-900">
                      {level.count || 0}
                    </td>
                  ))}
                  <td className="px-3 py-2 text-center text-gray-900">
                    {tosData.total_questions || 0}
                  </td>
                </tr>
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* Question Type Distribution */}
      {tosData.question_type_distribution && Object.keys(tosData.question_type_distribution).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Question Type Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
              {Object.entries(tosData.question_type_distribution).map(([type, count]) => (
                <div key={type} className="border rounded-lg p-4 text-center">
                  <p className="text-sm text-gray-600 mb-1 capitalize">
                    {type.replace(/_/g, ' ')}
                  </p>
                  <p className="text-2xl font-bold text-gray-900">{count}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    {tosData.total_questions > 0 
                      ? Math.round((count / tosData.total_questions) * 100) 
                      : 0}%
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Print Footer */}
      <div className="hidden print:block mt-8 pt-4 border-t text-center text-sm text-gray-600">
        <p>Generated on {new Date().toLocaleDateString()}</p>
      </div>
    </div>
  );
}

export default ReviewTOS;