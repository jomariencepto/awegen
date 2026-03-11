import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { AlertCircle, FileText, Clock } from 'lucide-react';
import api from '../../utils/api';

function PendingApprovals() {
  const [exams, setExams] = useState([]);
  const [filteredExams, setFilteredExams] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchPendingExams();
  }, []);

  useEffect(() => {
    if (searchTerm) {
      setFilteredExams(exams.filter(exam => 
        exam.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (exam.teacher_name && exam.teacher_name.toLowerCase().includes(searchTerm.toLowerCase()))
      ));
    } else {
      setFilteredExams(exams);
    }
  }, [searchTerm, exams]);

  const fetchPendingExams = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      console.log('Fetching pending exams...');
      
      // Use the correct endpoint - get exams with pending status
      const response = await api.get('/departments/exams', {
        params: { status: 'pending' }
      });
      
      console.log('Pending exams response:', response.data);
      
      if (response.data.success) {
        const pendingExams = response.data.exams || [];
        setExams(pendingExams);
        setFilteredExams(pendingExams);
      } else {
        setError(response.data.message || 'Failed to load pending exams');
        setExams([]);
        setFilteredExams([]);
      }
    } catch (error) {
      console.error('Error fetching pending exams:', error);
      const errorMsg = error.response?.data?.message || 'Failed to load pending exams';
      setError(errorMsg);
      setExams([]);
      setFilteredExams([]);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading pending exams...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Pending Approvals</h1>
            <p className="mt-1 text-sm text-gray-600">
              Review and approve exams submitted by teachers
            </p>
          </div>
        </div>
        
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-lg">
              <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0" />
              <div>
                <p className="font-medium text-red-900">Error loading pending exams</p>
                <p className="text-sm text-red-700 mt-1">{error}</p>
              </div>
            </div>
            <div className="mt-4">
              <Button onClick={fetchPendingExams} variant="outline">
                Try Again
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Pending Approvals</h1>
          <p className="mt-1 text-sm text-gray-600">
            Review and approve exams submitted by teachers
          </p>
        </div>
        <div className="flex items-center gap-2 mt-4 md:mt-0">
          <Badge variant="secondary" className="text-sm">
            {exams.length} pending
          </Badge>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Search Exams</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="search">Search by title or teacher</Label>
            <Input
              id="search"
              placeholder="Search exams..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      {filteredExams.length === 0 ? (
        <Card>
          <CardContent className="pt-6">
            <div className="text-center py-12">
              <div className="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
                <FileText className="h-8 w-8 text-green-600" />
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-1">
                {searchTerm ? 'No exams found' : 'All caught up!'}
              </h3>
              <p className="text-gray-500">
                {searchTerm 
                  ? 'Try adjusting your search terms' 
                  : 'No pending exams to review at the moment'}
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredExams.map((exam) => (
            <Card key={exam.exam_id} className="hover:shadow-lg transition-shadow">
              <CardHeader>
                <div className="flex justify-between items-start">
                  <CardTitle className="text-lg line-clamp-2">{exam.title}</CardTitle>
                  <Badge variant="warning" className="ml-2 flex-shrink-0">
                    <Clock className="h-3 w-3 mr-1" />
                    Pending
                  </Badge>
                </div>
                <CardDescription>
                  {exam.total_questions} questions • {exam.duration_minutes} mins
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2 text-sm text-gray-600">
                  <p>
                    <span className="font-medium">Teacher:</span>{' '}
                    {exam.teacher_name || `Teacher ID: ${exam.teacher_id}`}
                  </p>
                  <p>
                    <span className="font-medium">Submitted:</span>{' '}
                    {exam.sent_to_department_at 
                      ? new Date(exam.sent_to_department_at).toLocaleDateString()
                      : exam.created_at 
                        ? new Date(exam.created_at).toLocaleDateString()
                        : 'N/A'}
                  </p>
                  <p>
                    <span className="font-medium">Passing Score:</span> {exam.passing_score}%
                  </p>
                  {exam.department_notes && (
                    <p className="text-xs bg-blue-50 p-2 rounded border border-blue-200">
                      <span className="font-medium">Notes:</span> {exam.department_notes}
                    </p>
                  )}
                </div>
                <div className="flex gap-2 pt-2">
                  <Button size="sm" asChild className="flex-1">
                    <Link to={`/department/exam-review/${exam.exam_id}`}>
                      Review Exam
                    </Link>
                  </Button>
                  <Button size="sm" variant="outline" asChild className="flex-1">
                    <Link to={`/department/exam-preview/${exam.exam_id}`}>
                      Preview
                    </Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Info Card */}
      <Card className="bg-blue-50 border-blue-200">
        <CardContent className="pt-6">
          <div className="flex items-start gap-3">
            <div className="bg-blue-100 rounded-full p-2">
              <AlertCircle className="h-5 w-5 text-blue-600" />
            </div>
            <div className="text-sm text-blue-900">
              <p className="font-semibold mb-1">Review Guidelines:</p>
              <ul className="list-disc list-inside space-y-1 text-blue-800">
                <li>Check if questions align with learning objectives</li>
                <li>Verify answer keys are correct</li>
                <li>Ensure proper difficulty distribution</li>
                <li>Review Table of Specification (TOS)</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default PendingApprovals;