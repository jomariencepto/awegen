import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '../../components/ui/card';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue
} from '../../components/ui/select';
import { Progress } from '../../components/ui/progress';
import { Badge } from '../../components/ui/badge';
import { Upload, FileText, CheckCircle, X, AlertCircle, BookOpen, Trash2, Edit, Search, HelpCircle, Loader2 } from 'lucide-react';
import { toast } from 'react-hot-toast';
import { useAuth } from '../../context/AuthContext';
import api from '../../utils/api';

function UploadModule() {
  const navigate = useNavigate();
  const { currentUser } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatus, setUploadStatus] = useState('idle');
  const [subjects, setSubjects] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [currentFileIndex, setCurrentFileIndex] = useState(0);
  const [uploadResults, setUploadResults] = useState({ success: 0, failed: 0 });
  
  // States for modules display
  const [modules, setModules] = useState([]);
  const [filteredModules, setFilteredModules] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [subjectFilter, setSubjectFilter] = useState('all');
  const [isModulesLoading, setIsModulesLoading] = useState(true);

  const overlayStyle = {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.35)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 9999,
    backdropFilter: 'blur(2px)'
  };
  const cardStyle = {
    background: '#fff',
    padding: '16px 20px',
    borderRadius: '12px',
    boxShadow: '0 12px 30px rgba(0,0,0,0.12)',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    fontWeight: 600,
    color: '#111827'
  };
  const spinStyle = { animation: 'spin 1s linear infinite', color: '#f59e0b' };

  const {
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm();

  const selectedSubjectId = watch('subject_id');
  const formatSubjectLabel = (subject) => subject?.subject_name || 'Unnamed Subject';
  const groupedSubjects = useMemo(() => {
    const normalizedDepartments = (departments || [])
      .map((department) => ({
        id: department?.department_id ?? department?.id ?? null,
        name: String(department?.department_name || department?.name || '').trim()
      }))
      .filter((department) => department.name.length > 0);

    const groups = normalizedDepartments.map((department) => ({
      key: `dep-${department.id ?? department.name.toLowerCase()}`,
      departmentName: department.name,
      subjects: []
    }));

    const groupsByDepartmentId = new Map();
    const groupsByDepartmentName = new Map();

    normalizedDepartments.forEach((department, idx) => {
      const group = groups[idx];
      if (department.id !== null && department.id !== undefined && department.id !== '') {
        groupsByDepartmentId.set(Number(department.id), group);
      }
      groupsByDepartmentName.set(department.name.toLowerCase(), group);
    });

    subjects.forEach((subject) => {
      let group = null;
      if (subject?.department_id !== null && subject?.department_id !== undefined) {
        group = groupsByDepartmentId.get(Number(subject.department_id)) || null;
      }
      if (!group && subject?.department_name) {
        group = groupsByDepartmentName.get(String(subject.department_name).trim().toLowerCase()) || null;
      }

      if (!group) {
        const fallbackName = String(subject?.department_name || 'Other Department').trim();
        const fallbackKey = fallbackName.toLowerCase();
        group = groupsByDepartmentName.get(fallbackKey) || null;
        if (!group) {
          group = {
            key: `fallback-${fallbackKey.replace(/\s+/g, '-')}`,
            departmentName: fallbackName,
            subjects: []
          };
          groups.push(group);
          groupsByDepartmentName.set(fallbackKey, group);
        }
      }

      group.subjects.push(subject);
    });

    return groups;
  }, [departments, subjects]);

  useEffect(() => {
    const fetchLookups = async () => {
      try {
        const [subjectsResponse, departmentsResponse] = await Promise.all([
          api.get('/users/subjects'),
          api.get('/departments')
        ]);
        setSubjects(subjectsResponse.data.subjects || []);
        setDepartments(departmentsResponse.data.departments || []);
      } catch (error) {
        console.error('Error fetching subjects:', error);
        toast.error('Failed to load subjects and departments');
      }
    };

    fetchLookups();
    fetchModules();
  }, []);

  useEffect(() => {
    let result = [...modules];
    
    if (searchTerm.trim() !== '') {
      const term = searchTerm.toLowerCase();
      result = result.filter(module =>
        module.title?.toLowerCase().includes(term) ||
        module.subject_name?.toLowerCase().includes(term)
      );
    }
    
    if (subjectFilter !== 'all') {
      result = result.filter(module => module.subject_id === Number(subjectFilter));
    }
    
    setFilteredModules(result);
  }, [modules, searchTerm, subjectFilter]);

  const fetchModules = async () => {
    if (!currentUser?.user_id) {
      setIsModulesLoading(false);
      return;
    }

    try {
      setIsModulesLoading(true);
      const response = await api.get(`/modules/teacher/${currentUser.user_id}`);
      setModules(response.data.modules || []);
      setFilteredModules(response.data.modules || []);
    } catch (error) {
      console.error('Error fetching modules:', error);
      toast.error('Failed to load modules');
    } finally {
      setIsModulesLoading(false);
    }
  };

  // Auto-poll every 3s while any module is still processing
  useEffect(() => {
    const hasProcessing = modules.some(
      m => m.processing_status === 'pending' || m.processing_status === 'processing'
    );
    if (!hasProcessing) return;

    const timer = setInterval(() => {
      fetchModules();
    }, 3000);

    return () => clearInterval(timer);
  }, [modules]);

  const handleFileChange = (e) => {
    const files = Array.from(e.target.files);
    if (!files.length) return;

    const allowedTypes = ['pdf', 'doc', 'docx'];
                          
    const maxSize = 16 * 1024 * 1024;

    const invalidFiles = files.filter(file => {
      const ext = file.name.split('.').pop().toLowerCase();
      return !allowedTypes.includes(ext);
    });

    if (invalidFiles.length) {
      toast.error(`Invalid file(s): ${invalidFiles.map(f => f.name).join(', ')}`);
      return;
    }

    const oversizedFiles = files.filter(file => file.size > maxSize);
    if (oversizedFiles.length) {
      toast.error(`File too large (max 16MB): ${oversizedFiles.map(f => f.name).join(', ')}`);
      return;
    }

    setSelectedFiles(prev => [...prev, ...files]);
  };

  const removeFile = (index) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const uploadSingleFile = async (file, subjectId) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('subject_id', subjectId);

    return api.post('/modules/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        const progress = Math.round((e.loaded * 100) / e.total);
        setUploadProgress(progress);
      },
    });
  };

  const handleDeleteModule = async (moduleId) => {
    if (!window.confirm('Are you sure you want to delete this module? This action cannot be undone.')) {
      return;
    }

    try {
      await api.delete(`/modules/${moduleId}`);
      setModules(prev => prev.filter(module => module.module_id !== moduleId));
      toast.success('Module deleted successfully');
    } catch (error) {
      console.error('Error deleting module:', error);
      toast.error(error.response?.data?.message || 'Failed to delete module');
    }
  };

  const onSubmit = async (data) => {
    if (!selectedFiles.length) {
      toast.error('Please select at least one file');
      return;
    }

    if (!data.subject_id) {
      toast.error('Please select a subject');
      return;
    }

    setIsLoading(true);
    setUploadStatus('uploading');
    setUploadResults({ success: 0, failed: 0 });

    let success = 0;
    let failed = 0;

    try {
      for (let i = 0; i < selectedFiles.length; i++) {
        setCurrentFileIndex(i);
        setUploadProgress(0);

        try {
          await uploadSingleFile(selectedFiles[i], data.subject_id);
          success++;
          setUploadResults(prev => ({ ...prev, success }));
          toast.success(`${selectedFiles[i].name} uploaded`);
        } catch (error) {
          failed++;
          setUploadResults(prev => ({ ...prev, failed }));
          toast.error(`${selectedFiles[i].name} failed`);
        }
      }

      if (success > 0) {
        setUploadStatus('success');
        toast.success(
          failed > 0
            ? `${success} uploaded, ${failed} failed`
            : `All ${success} module(s) uploaded`
        );

        // Refresh modules list after successful upload
        fetchModules();
        
        // Reset form
        setSelectedFiles([]);
        setUploadStatus('idle');
      } else {
        setUploadStatus('error');
        toast.error('All uploads failed');
      }
    } catch {
      setUploadStatus('error');
      toast.error('Upload failed');
    } finally {
      setIsLoading(false);
      setCurrentFileIndex(0);
    }
  };

  return (
    <div className="space-y-6 bg-gradient-to-b from-amber-50/30 to-white rounded-xl p-1">
      <style>{`@keyframes spin { from {transform: rotate(0deg);} to {transform: rotate(360deg);} }`}</style>
      {isLoading && (
        <div style={overlayStyle}>
          <div style={cardStyle}>
            <Loader2 style={spinStyle} size={28} />
            <p>Uploading modules...</p>
          </div>
        </div>
      )}
      {/* Page Header */}
      <div className="rounded-xl border border-amber-200 bg-white shadow-sm px-5 py-4">
        <h1 className="text-3xl font-bold text-amber-900">Upload Modules</h1>
        <p className="text-amber-800">
          Upload learning materials to generate exams
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Upload Form */}
        <Card className="bg-white border border-amber-200 shadow-sm rounded-xl">
          <CardHeader>
            <CardTitle className="text-amber-900">Upload New Module</CardTitle>
            <CardDescription className="text-amber-800">Select a subject and upload files</CardDescription>
          </CardHeader>

          <form onSubmit={handleSubmit(onSubmit)}>
            <CardContent className="space-y-4">
              {/* Subject */}
              <div className="space-y-2">
                <Label>Subject *</Label>
                <Select
                  onValueChange={(value) => setValue('subject_id', Number(value))}
                  disabled={isLoading}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select subject" />
                  </SelectTrigger>
                  <SelectContent>
                    {groupedSubjects.map((group, groupIndex) => (
                      <React.Fragment key={`upload-group-${group.departmentName}`}>
                        <SelectGroup>
                          <SelectLabel className="bg-yellow-50 text-yellow-800 rounded-sm">
                            {group.departmentName}
                          </SelectLabel>
                          {group.subjects.length === 0 && (
                            <SelectItem value={`__empty-upload-${group.key}`} disabled>
                              No subjects yet
                            </SelectItem>
                          )}
                          {group.subjects.map((subject) => (
                            <SelectItem
                              key={subject.subject_id}
                              value={subject.subject_id.toString()}
                            >
                              {formatSubjectLabel(subject)}
                            </SelectItem>
                          ))}
                        </SelectGroup>
                        {groupIndex < groupedSubjects.length - 1 && <SelectSeparator />}
                      </React.Fragment>
                    ))}
                  </SelectContent>
                </Select>
                {errors.subject_id && (
                  <p className="text-sm text-red-500">Subject is required</p>
                )}
              </div>

              {/* File Upload */}
              <div className="space-y-2">
                <Label>Upload Files *</Label>
                <label className="flex flex-col items-center justify-center h-64 border-2 border-dashed border-amber-200 rounded-xl cursor-pointer bg-amber-50/40 hover:bg-amber-50">
                  {uploadStatus === 'success' ? (
                    <CheckCircle className="w-10 h-10 text-green-500" />
                  ) : uploadStatus === 'error' ? (
                    <AlertCircle className="w-10 h-10 text-red-500" />
                  ) : (
                    <Upload className="w-10 h-10 text-yellow-500" />
                  )}
                  <p className="text-sm mt-2 text-amber-800">
                    Click or drag files here (PDF, DOCX). Full module content is extracted automatically.
                  </p>
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.doc,.docx"
                    className="hidden"
                    onChange={handleFileChange}
                    disabled={isLoading}
                  />
                </label>

                {selectedFiles.length > 0 && (
                  <div className="space-y-2 mt-4 max-h-40 overflow-y-auto">
                    {selectedFiles.map((file, index) => (
                      <div
                        key={`${file.name}-${file.lastModified}-${index}`}
                        className={`flex items-center p-2 border rounded ${
                          uploadStatus === 'uploading' && index === currentFileIndex
                            ? 'border-yellow-500 bg-yellow-50'
                            : ''
                        }`}
                      >
                        <FileText className="w-5 h-5 text-yellow-500 mr-2" />
                        <span className="flex-1 truncate text-sm">{file.name}</span>
                        <button
                          type="button"
                          onClick={() => removeFile(index)}
                          disabled={isLoading}
                        >
                          <X className="w-4 h-4 text-gray-500 hover:text-red-500" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {uploadStatus === 'uploading' && (
                  <div className="mt-4">
                    <Progress value={uploadProgress} />
                    <p className="text-xs text-center mt-1 text-gray-500">
                      Uploading file {currentFileIndex + 1} of {selectedFiles.length}
                    </p>
                  </div>
                )}
              </div>
            </CardContent>

            <CardFooter>
              <Button
                type="submit"
                className="w-full bg-amber-500 hover:bg-amber-600 text-white"
                disabled={isLoading || !selectedFiles.length || !selectedSubjectId}
              >
                Upload {selectedFiles.length || ''} Module{selectedFiles.length !== 1 ? 's' : ''}
              </Button>
            </CardFooter>
          </form>
        </Card>

        {/* Uploaded Modules */}
        <Card className="bg-white border border-amber-200 shadow-sm rounded-xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-amber-700" />
              Your Modules
            </CardTitle>
            <CardDescription className="text-amber-800">View and manage your uploaded modules</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Search and Filter */}
            <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_220px] gap-3">
              <div className="relative min-w-0">
                <Input
                  placeholder="Search modules..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 h-10 border-amber-200 focus-visible:ring-amber-500"
                />
              </div>
              <div className="w-full md:w-[220px]">
                <Select value={subjectFilter} onValueChange={setSubjectFilter}>
                  <SelectTrigger className="w-full h-10 border-amber-200 focus:ring-amber-500">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Subjects</SelectItem>
                    {groupedSubjects.length > 0 && <SelectSeparator />}
                    {groupedSubjects.map((group, groupIndex) => (
                      <React.Fragment key={`filter-group-${group.departmentName}`}>
                        <SelectGroup>
                          <SelectLabel className="bg-yellow-50 text-yellow-800 rounded-sm">
                            {group.departmentName}
                          </SelectLabel>
                          {group.subjects.length === 0 && (
                            <SelectItem value={`__empty-filter-${group.key}`} disabled>
                              No subjects yet
                            </SelectItem>
                          )}
                          {group.subjects.map((subject) => (
                            <SelectItem key={subject.subject_id} value={subject.subject_id.toString()}>
                              {formatSubjectLabel(subject)}
                            </SelectItem>
                          ))}
                        </SelectGroup>
                        {groupIndex < groupedSubjects.length - 1 && <SelectSeparator />}
                      </React.Fragment>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs text-amber-800">
              <span>
                Showing {filteredModules.length} of {modules.length} module(s)
              </span>
              {searchTerm && (
                <button
                  type="button"
                  className="underline underline-offset-2 hover:text-amber-900"
                  onClick={() => setSearchTerm('')}
                >
                  Clear search
                </button>
              )}
            </div>

            {/* Modules List */}
            {isModulesLoading ? (
              <div className="flex justify-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-yellow-500"></div>
              </div>
            ) : filteredModules.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <BookOpen className="mx-auto h-12 w-12 text-gray-300 mb-2" />
                <p>No modules found</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-[500px] overflow-y-auto pr-2">
                {filteredModules.map(module => (
                  <div key={module.module_id} className="flex items-start justify-between p-3 border border-amber-200 rounded-xl bg-white hover:bg-amber-50/40">
                    <div className="flex-1 min-w-0">
                      <h4 className="font-semibold text-sm text-amber-950 truncate">{module.title}</h4>
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        <Badge variant="outline" className="text-xs">
                          {module.subject_name || 'Unknown'}
                        </Badge>

                        {/* Processing status / question count badge */}
                        {(module.processing_status === 'pending' || module.processing_status === 'processing') && (
                          <Badge className="text-xs bg-yellow-50 text-yellow-700 border border-yellow-200 flex items-center gap-1">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            Processing...
                          </Badge>
                        )}
                        {module.processing_status === 'failed' && (
                          <Badge className="text-xs bg-red-50 text-red-700 border border-red-200">
                            Processing failed
                          </Badge>
                        )}
                        {module.processing_status === 'completed' && (
                          <Badge className="text-xs bg-green-50 text-green-700 border border-green-200 flex items-center gap-1">
                            <CheckCircle className="h-3 w-3" />
                            Processed
                          </Badge>
                        )}

                        <span className="text-xs text-gray-400">
                          {new Date(module.created_at).toLocaleDateString()}
                        </span>
                      </div>

                      {/* Difficulty breakdown hidden intentionally */}
                    </div>
                    <div className="flex gap-1 ml-2 shrink-0">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-8 w-8 p-0"
                        title="Edit"
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-8 w-8 p-0 text-red-500 hover:text-red-700"
                        onClick={() => handleDeleteModule(module.module_id)}
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default UploadModule;


