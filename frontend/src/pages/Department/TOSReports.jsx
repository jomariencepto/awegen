import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Download } from 'lucide-react';
import api from '../../utils/api';

function TOSReports() {
  const [exams, setExams] = useState([]);
  const [filteredExams, setFilteredExams] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchExams();
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

  const fetchExams = async () => {
    try {
      // FIXED: Added '/departments' prefix to match the backend Blueprint route
      const response = await api.get('/departments/exams/department/all');
      setExams(response.data.exams || []);
      setFilteredExams(response.data.exams || []);
    } catch (error) {
      console.error('Error fetching exams:', error);
      setExams([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownloadTOS = async (examId, examTitle) => {
    try {
      // Export service provides PDF at /exports/tos/<exam_id>/pdf
      const response = await api.get(`/exports/tos/${examId}/pdf`, {
        responseType: 'blob',
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `TOS-${examTitle}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error downloading TOS:', error);
      alert('Failed to download TOS. Please ensure the report exists and try again.');
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-yellow-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading TOS reports...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-amber-900">Table of Specification Reports</h1>
        <p className="mt-1 text-sm text-amber-700">
          View and download TOS reports for all exams
        </p>
      </div>

      <Card className="bg-white border border-amber-200 shadow-lg shadow-amber-200/60">
        <CardHeader>
          <CardTitle className="text-lg text-amber-900">Search Exams</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="search" className="text-amber-800">Search by title</Label>
            <Input
              id="search"
              placeholder="Search exams..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="border-amber-200 focus:ring-amber-400 focus:border-amber-400"
            />
          </div>
        </CardContent>
      </Card>

      {filteredExams.length === 0 ? (
        <Card className="bg-white border border-amber-200 shadow-md shadow-amber-200/50">
          <CardContent className="pt-6">
            <div className="text-center py-12">
              <div className="text-amber-300 text-5xl mb-4">📊</div>
              <h3 className="text-lg font-medium text-amber-900 mb-1">No exams found</h3>
              <p className="text-amber-700">
                {searchTerm ? 'Try adjusting your search' : 'No exams available yet'}
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filteredExams.map((exam) => (
            <Card key={exam.exam_id} className="bg-white border border-amber-200 shadow-lg shadow-amber-200/60">
              <CardHeader>
                <div className="flex justify-between items-start gap-3">
                  <div className="flex-1">
                    <CardTitle className="text-lg text-amber-900">{exam.title}</CardTitle>
                    <CardDescription className="mt-1 text-amber-700">
                      {exam.teacher_name} • {exam.total_questions} questions • {exam.duration_minutes} mins
                    </CardDescription>
                  </div>
                  <Badge className="bg-amber-500 text-amber-950 border border-amber-300">
                    {exam.status}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between gap-4 flex-wrap">
                  <div className="space-y-1 text-sm text-amber-800">
                    <p>
                      <span className="font-semibold">Created:</span>{' '}
                      {new Date(exam.created_at).toLocaleDateString()}
                    </p>
                    <p>
                      <span className="font-semibold">Passing Score:</span> {exam.passing_score}%
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleDownloadTOS(exam.exam_id, exam.title)}
                    className="border-amber-300 text-amber-900 hover:bg-amber-50"
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Download TOS
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

export default TOSReports;
