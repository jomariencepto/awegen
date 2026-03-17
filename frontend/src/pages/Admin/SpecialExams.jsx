import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import api from '../../utils/api';

function SpecialExams() {
  const [exams, setExams] = useState([]);
  const [filteredExams, setFilteredExams] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchSpecialExams();
  }, []);

  useEffect(() => {
    if (searchTerm) {
      setFilteredExams(exams.filter(exam => 
        exam.title.toLowerCase().includes(searchTerm.toLowerCase())
      ));
    } else {
      setFilteredExams(exams);
    }
  }, [searchTerm, exams]);

  const fetchSpecialExams = async () => {
    try {
      const response = await api.get('/exams/special');
      setExams(response.data.exams || []);
      setFilteredExams(response.data.exams || []);
    } catch (error) {
      console.error('Error fetching special exams:', error);
      setExams([]);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleSpecialStatus = async (examId, currentStatus) => {
    try {
      const response = await api.put(`/exams/${examId}/special`, {
        is_special: !currentStatus
      });

      const updatedExam = response.data?.exam;
      setExams(exams.map(exam => 
        exam.exam_id === examId 
          ? { ...exam, ...(updatedExam || {}), is_special: !currentStatus }
          : exam
      ));
    } catch (error) {
      console.error('Error updating special status:', error);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading special exams...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Special Exams</h1>
          <p className="mt-1 text-sm text-gray-600">
            Manage exams marked as special or priority
          </p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Search Exams</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="search">Search by title</Label>
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
              <div className="text-gray-400 text-5xl mb-4">📋</div>
              <h3 className="text-lg font-medium text-gray-900 mb-1">No special exams found</h3>
              <p className="text-gray-500">
                {searchTerm ? 'Try adjusting your search' : 'No exams have been marked as special yet'}
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredExams.map((exam) => (
            <Card key={exam.exam_id}>
              <CardHeader>
                <div className="flex justify-between items-start">
                  <CardTitle className="text-lg">{exam.title}</CardTitle>
                  {exam.is_special && (
                    <Badge variant="default">Special</Badge>
                  )}
                </div>
                <CardDescription>
                  {exam.total_questions} questions • {exam.duration_minutes} mins
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2 text-sm text-gray-600">
                  <p>
                    <span className="font-medium">Created:</span>{' '}
                    {new Date(exam.created_at).toLocaleDateString()}
                  </p>
                  <p>
                    <span className="font-medium">Status:</span>{' '}
                    <Badge variant="outline">{exam.status || exam.admin_status || 'approved'}</Badge>
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant={exam.is_special ? 'destructive' : 'default'}
                    onClick={() => toggleSpecialStatus(exam.exam_id, exam.is_special)}
                    className="flex-1"
                  >
                    {exam.is_special ? 'Remove Special' : 'Mark Special'}
                  </Button>
                  <Button size="sm" variant="outline" asChild>
                    <Link to={`/admin/exams/${exam.exam_id}`}>View</Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

export default SpecialExams;
