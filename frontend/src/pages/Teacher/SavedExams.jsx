import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '../../components/ui/select';
import api from '../../utils/api';

function SavedExams() {
  const [exams, setExams] = useState([]);
  const [filteredExams, setFilteredExams] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [subjectFilter, setSubjectFilter] = useState('all');
  const [subjects, setSubjects] = useState([]);
  
  // State for Departments fetched from DB
  const [departments, setDepartments] = useState([]);
  const [departmentsLoading, setDepartmentsLoading] = useState(true);
  const [departmentsError, setDepartmentsError] = useState(null);
  
  // Tracks selected department for each exam card
  const [selectedDepartments, setSelectedDepartments] = useState({}); 

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchSavedExams = async () => {
      try {
        setIsLoading(true);
        setError(null);
        
        const response = await api.get('/exams/saved-exams');
        console.log('Saved exams response:', response.data);
        
        const examsData = (response.data.exams || []).filter(
          exam => exam.admin_status === 'draft'
        );

        setExams(examsData);
        setFilteredExams(examsData);

        // Extract unique subjects
        const uniqueSubjects = Array.from(
          new Set(examsData.map(exam => exam.subject_name).filter(Boolean))
        );
        setSubjects(uniqueSubjects);
      } catch (error) {
        console.error('Error fetching saved exams:', error);
        setError(error.response?.data?.message || 'Failed to load saved exams');
      } finally {
        setIsLoading(false);
      }
    };

    const fetchDepartments = async () => {
      try {
        setDepartmentsLoading(true);
        setDepartmentsError(null);
        
        console.log('Fetching departments from /api/departments...');
        const response = await api.get('/departments');
        console.log('Raw departments response:', response.data);
        
        if (response.data.success) {
          const depts = response.data.departments || [];
          console.log('Departments array:', depts);
          
          // Validate department data
          const validDepts = depts.filter(dept => {
            const hasId = dept.id || dept.department_id;
            const hasName = dept.name || dept.department_name;
            if (!hasId || !hasName) {
              console.warn('Invalid department data:', dept);
              return false;
            }
            return true;
          });
          
          console.log('Valid departments:', validDepts);
          setDepartments(validDepts);
          
          if (validDepts.length === 0 && depts.length > 0) {
            setDepartmentsError('Department data is missing required fields');
          }
        } else {
          throw new Error(response.data.message || 'Failed to load departments');
        }
      } catch (err) {
        console.error('Error fetching departments:', err);
        console.error('Error details:', {
          message: err.message,
          response: err.response?.data,
          status: err.response?.status
        });
        setDepartmentsError(err.response?.data?.message || err.message || 'Failed to load departments');
        setDepartments([]);
      } finally {
        setDepartmentsLoading(false);
      }
    };

    fetchSavedExams();
    fetchDepartments();
  }, []);

  useEffect(() => {
    let result = [...exams]; 

    if (searchTerm.trim() !== '') {
      const term = searchTerm.toLowerCase();
      result = result.filter(exam =>
        exam.title?.toLowerCase().includes(term) ||
        exam.subject_name?.toLowerCase().includes(term)
      );
    }

    if (subjectFilter !== 'all') {
      result = result.filter(exam => exam.subject_name === subjectFilter);
    }

    setFilteredExams(result);
  }, [exams, searchTerm, subjectFilter]);

  const handleDepartmentChange = (examId, departmentId) => {
    setSelectedDepartments(prev => ({
      ...prev,
      [examId]: departmentId
    }));
  };

  const handleSubmitForApproval = async (examId) => {
    const departmentId = selectedDepartments[examId];

    if (!departmentId) {
      alert('Please select a department before submitting.');
      return;
    }

    try {
      await api.post(`/exams/${examId}/submit`, {
        exam_id: examId,
        department_id: departmentId,
        instructor_notes: 'Submitted for approval'
      });
      
      setExams(prev => prev.filter(exam => exam.exam_id !== examId));
      setSelectedDepartments(prev => {
        const newState = { ...prev };
        delete newState[examId];
        return newState;
      });

      alert('Exam submitted for approval successfully!');
    } catch (error) {
      console.error('Error submitting exam for approval:', error);
      alert(error.response?.data?.message || 'Failed to submit exam for approval');
    }
  };

  const handleDeleteExam = async (examId) => {
    if (!window.confirm('Are you sure you want to delete this exam? This action cannot be undone.')) {
      return;
    }

    try {
      await api.delete(`/exams/${examId}`);
      setExams(prev => prev.filter(exam => exam.exam_id !== examId));
      alert('Exam deleted successfully!');
    } catch (error) {
      console.error('Error deleting exam:', error);
      alert(error.response?.data?.message || 'Failed to delete exam');
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-yellow-500 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading saved exams...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <Card className="bg-white border border-red-200 shadow-sm max-w-md">
          <CardContent className="py-8 text-center">
            <div className="text-5xl mb-4">⚠️</div>
            <h3 className="text-lg font-medium mb-2 text-red-700">Error Loading Exams</h3>
            <p className="text-gray-600 mb-4">{error}</p>
            <Button 
              onClick={() => window.location.reload()} 
              className="bg-yellow-500 hover:bg-yellow-600 text-black"
            >
              Try Again
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Saved Exams</h1>
          <p className="mt-1 text-sm text-gray-600">
            Exams saved as drafts and not yet submitted ({exams.length} total)
          </p>
        </div>

        <div className="mt-4 md:mt-0">
          <Link to="/teacher/create-exam">
            <Button className="bg-yellow-500 hover:bg-yellow-600 text-black">
              Create New Exam
            </Button>
          </Link>
        </div>
      </div>

      {/* Department Loading Warning */}
      {departmentsLoading && (
        <Card className="bg-blue-50 border border-blue-200 shadow-sm">
          <CardContent className="py-4">
            <div className="flex items-center gap-2">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
              <p className="text-sm text-blue-700">Loading departments...</p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Department Error Warning */}
      {departmentsError && !departmentsLoading && (
        <Card className="bg-yellow-50 border border-yellow-200 shadow-sm">
          <CardContent className="py-4">
            <div className="flex items-start gap-2">
              <span className="text-yellow-600 text-xl">⚠️</span>
              <div className="flex-1">
                <p className="text-sm font-medium text-yellow-800">Warning: Departments Not Available</p>
                <p className="text-xs text-yellow-700 mt-1">{departmentsError}</p>
                <p className="text-xs text-yellow-600 mt-2">You won't be able to submit exams until departments are loaded.</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      {exams.length > 0 && (
        <Card className="bg-white border border-gray-200 shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg">Filter Exams</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="search">Search</Label>
              <Input
                id="search"
                placeholder="Search by title or subject..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label>Subject</Label>
              <Select value={subjectFilter} onValueChange={setSubjectFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="All subjects" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Subjects</SelectItem>
                  {subjects.map(subject => (
                    <SelectItem key={subject} value={subject}>
                      {subject}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Empty State */}
      {filteredExams.length === 0 ? (
        <Card className="bg-white border border-gray-200 shadow-sm">
          <CardContent className="py-12 text-center">
            <div className="text-5xl mb-4">💾</div>
            <h3 className="text-lg font-medium mb-1">No saved exams found</h3>
            <p className="text-gray-500 mb-4">
              {searchTerm || subjectFilter !== 'all'
                ? 'Try adjusting your filters'
                : 'Create your first exam to get started'}
            </p>
            <Link to="/teacher/create-exam">
              <Button className="bg-yellow-500 hover:bg-yellow-600 text-black">
                Create New Exam
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredExams.map(exam => (
            <Card
              key={exam.exam_id}
              className="flex flex-col bg-white border border-gray-200 shadow-sm hover:shadow-md transition-shadow"
            >
              <CardHeader>
                <div className="flex justify-between items-start">
                  <CardTitle className="text-lg line-clamp-2">{exam.title}</CardTitle>
                  <Badge variant="secondary" className="ml-2 shrink-0">Draft</Badge>
                </div>
                <CardDescription className="line-clamp-1">
                  {exam.subject_name || 'Unknown Subject'} • {exam.total_questions || 0} questions
                </CardDescription>
              </CardHeader>

              <CardContent className="text-sm text-gray-600 space-y-1 flex-1">
                {exam.description && (
                  <p className="text-gray-700 mb-2 line-clamp-2">{exam.description}</p>
                )}
                <p><strong>Created:</strong> {new Date(exam.created_at).toLocaleDateString()}</p>
                <p><strong>Duration:</strong> {exam.duration_minutes || 0} minutes</p>
                <p><strong>Passing:</strong> {exam.passing_score || 0}%</p>
              </CardContent>

              <CardContent className="pt-0 flex flex-col gap-3">
                {/* Top Row: Preview, Edit, Delete */}
                <div className="flex flex-wrap gap-2">
                  <Link to={`/teacher/exam-preview/${exam.exam_id}`}>
                    <Button size="sm" variant="outline" className="border-yellow-500 text-yellow-700 hover:bg-yellow-50">
                      Preview
                    </Button>
                  </Link>

                  <Link to={`/teacher/edit-exam/${exam.exam_id}`}>
                    <Button size="sm" variant="outline" className="border-yellow-500 text-yellow-700 hover:bg-yellow-50">
                      Edit
                    </Button>
                  </Link>

                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleDeleteExam(exam.exam_id)}
                    className="border-red-200 text-red-600 hover:bg-red-50"
                  >
                    Delete
                  </Button>
                </div>

                {/* Bottom Row: Department Selection & Submit */}
                <div className="pt-2 border-t border-gray-100 space-y-2">
                  <Label htmlFor={`dept-select-${exam.exam_id}`} className="text-xs font-semibold text-gray-500">
                    Submit to Department
                  </Label>
                  <div className="flex gap-2">
                    <Select 
                      value={selectedDepartments[exam.exam_id] || ""} 
                      onValueChange={(value) => handleDepartmentChange(exam.exam_id, value)}
                      disabled={departmentsLoading || departments.length === 0}
                    >
                      <SelectTrigger id={`dept-select-${exam.exam_id}`} className="flex-1 h-9 text-sm">
                        <SelectValue placeholder={
                          departmentsLoading 
                            ? "Loading..." 
                            : departments.length === 0 
                            ? "No Departments" 
                            : "Select Department..."
                        } />
                      </SelectTrigger>
                      <SelectContent>
                        {departments && departments.length > 0 && departments.map(dept => (
                          <SelectItem 
                            key={dept.id || dept.department_id} 
                            value={(dept.id || dept.department_id).toString()}
                          >
                            {dept.name || dept.department_name || 'Unknown Department'}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    
                    <Button
                      size="sm"
                      onClick={() => handleSubmitForApproval(exam.exam_id)}
                      disabled={!selectedDepartments[exam.exam_id] || departmentsLoading}
                      className="bg-green-600 hover:bg-green-700 text-white whitespace-nowrap disabled:bg-gray-300 disabled:cursor-not-allowed"
                    >
                      Submit
                    </Button>
                  </div>
                  {departmentsError && (
                    <p className="text-xs text-red-500">⚠️ Cannot load departments. Check your connection.</p>
                  )}
                  {!departmentsError && departments.length === 0 && !departmentsLoading && (
                    <p className="text-xs text-amber-600">⚠️ No departments found in system.</p>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

export default SavedExams;
