import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import api from '../../utils/api';

function ApprovedExams() {
  const [exams, setExams] = useState([]);
  const [filteredExams, setFilteredExams] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchApprovedExams();
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

  const fetchApprovedExams = async () => {
    try {
      const perPage = 200;
      let page = 1;
      let pages = 1;
      const allExams = [];

      do {
        const response = await api.get('/departments/exams', {
          params: {
            status: 'approved',
            page,
            per_page: perPage,
          }
        });

        allExams.push(...(response.data.exams || []));
        pages = response.data.pages || 1;
        page += 1;
      } while (page <= pages);

      setExams(allExams);
      setFilteredExams(allExams);
    } catch (error) {
      console.error('Error fetching approved exams:', error);
      setExams([]);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading approved exams...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Approved Exams</h1>
          <p className="mt-1 text-sm text-gray-600">
            View all approved exams in your department
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
              <h3 className="text-lg font-medium text-gray-900 mb-1">No approved exams found</h3>
              <p className="text-gray-500">
                {searchTerm ? 'Try adjusting your search' : 'No exams have been approved yet'}
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
                  <Badge variant="default">Approved</Badge>
                </div>
                <CardDescription>
                  {exam.total_questions} questions • {exam.duration_minutes} mins
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2 text-sm text-gray-600">
                  <p>
                    <span className="font-medium">Teacher:</span> {exam.teacher_name || `Teacher ID: ${exam.teacher_id}`}
                  </p>
                  <p>
                    <span className="font-medium">Approved:</span>{' '}
                    {exam.reviewed_at ? new Date(exam.reviewed_at).toLocaleDateString() : 'N/A'}
                  </p>
                  <p>
                    <span className="font-medium">Passing Score:</span> {exam.passing_score}%
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" asChild className="flex-1">
                    <Link to={`/department/exam-preview/${exam.exam_id}`}>Preview</Link>
                  </Button>
                  <Button size="sm" variant="outline" asChild className="flex-1">
                    <Link to={`/department/tos-reports/${exam.exam_id}`}>TOS</Link>
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

export default ApprovedExams;
