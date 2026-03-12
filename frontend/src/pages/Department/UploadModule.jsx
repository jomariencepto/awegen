import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '../../components/ui/card';
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectSeparator, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Textarea } from '../../components/ui/textarea';
import { Progress } from '../../components/ui/progress';
import { Upload, FileText, CheckCircle } from 'lucide-react';
import { toast } from 'react-hot-toast';
import api from '../../utils/api';

function UploadModule() {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatus, setUploadStatus] = useState('idle');
  const [subjects, setSubjects] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const formatSubjectLabel = (subject) => subject?.subject_name || 'Unnamed Subject';
  const groupedSubjects = React.useMemo(() => {
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
  
  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm();

  React.useEffect(() => {
    // Fetch subjects and departments
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
  }, []);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const allowedTypes = ['pdf', 'doc', 'docx'];
    const maxSize = 50 * 1024 * 1024;
    const ext = file.name.split('.').pop()?.toLowerCase();

    if (!allowedTypes.includes(ext)) {
      toast.error(`Invalid file type: ${file.name}`);
      return;
    }

    if (file.size > maxSize) {
      toast.error(`File too large (max 50MB): ${file.name}`);
      return;
    }

    setSelectedFile(file);
    setValue('file', file);
  };

  const onSubmit = async (data) => {
    if (!selectedFile) {
      toast.error('Please select a file');
      return;
    }

    setIsLoading(true);
    setUploadStatus('uploading');
    
      try {
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('title', data.title);
        formData.append('description', data.description);
        formData.append('subject_id', data.subject_id);
        if (data.teaching_hours) {
          formData.append('teaching_hours', data.teaching_hours);
        }
      
      const response = await api.post('/modules/upload', formData, {
        onUploadProgress: (progressEvent) => {
          const progress = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          setUploadProgress(progress);
        },
      });
      
      setUploadStatus('success');
      toast.success('Module uploaded successfully!');
      
      // Redirect after a short delay
      setTimeout(() => {
        navigate('/department/dashboard');
      }, 2000);
      
    } catch (error) {
      setUploadStatus('error');
      const status = error.response?.status;
      const message = (
        error.response?.data?.message ||
        (status === 413 ? 'File too large. Maximum upload size is 50 MB.' : null) ||
        (status === 403 ? 'Your account does not have permission to upload modules.' : null) ||
        'Failed to upload module'
      );
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Upload Module</h1>
        <p className="text-muted-foreground">
          Upload a learning module and pick any subject from all departments
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Module Information</CardTitle>
          <CardDescription>
            Enter the details for the learning module
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit(onSubmit)}>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title">Module Title</Label>
              <Input
                id="title"
                placeholder="Introduction to Advanced Mathematics"
                {...register('title', {
                  required: 'Title is required',
                })}
              />
              {errors.title && (
                <p className="text-sm text-red-500">{errors.title.message}</p>
              )}
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                placeholder="Enter a description for the module"
                {...register('description', {
                  required: 'Description is required',
                })}
              />
              {errors.description && (
                <p className="text-sm text-red-500">{errors.description.message}</p>
              )}
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="subject_id">Subject</Label>
              <Select onValueChange={(value) => setValue('subject_id', parseInt(value))}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a subject" />
                </SelectTrigger>
                <SelectContent>
                  {groupedSubjects.map((group, groupIndex) => (
                    <React.Fragment key={`dept-group-${group.departmentName}`}>
                      <SelectGroup>
                        <SelectLabel className="bg-yellow-50 text-yellow-800 rounded-sm">
                          {group.departmentName}
                        </SelectLabel>
                        {group.subjects.length === 0 && (
                          <SelectItem value={`__empty-dept-${group.key}`} disabled>
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
              {errors.subject_id && (
                <p className="text-sm text-red-500">{errors.subject_id.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="teaching_hours">Teaching Hours (optional)</Label>
              <Input
                id="teaching_hours"
                type="number"
                min="0"
                placeholder="e.g. 12"
                {...register('teaching_hours')}
                disabled={isLoading}
              />
              <p className="text-xs text-gray-500">Prefills hours when creating exams; can be overridden.</p>
            </div>
             
            <div className="space-y-2">
              <Label htmlFor="file">Upload File</Label>
              <div className="flex items-center justify-center w-full">
                <label
                  htmlFor="file"
                  className="flex flex-col items-center justify-center w-full h-64 border-2 border-dashed rounded-lg cursor-pointer bg-gray-50 hover:bg-gray-100"
                >
                  <div className="flex flex-col items-center justify-center pt-5 pb-6">
                    {uploadStatus === 'success' ? (
                      <CheckCircle className="w-10 h-10 mb-3 text-green-500" />
                    ) : (
                      <Upload className="w-10 h-10 mb-3 text-gray-400" />
                    )}
                    <p className="mb-2 text-sm text-gray-500">
                      <span className="font-semibold">Click to upload</span> or drag and drop
                    </p>
                    <p className="text-xs text-gray-500">
                      PDF, DOC, DOCX, PPT, PPTX, TXT (MAX. 50MB)
                    </p>
                  </div>
                  <input
                    id="file"
                    type="file"
                    className="hidden"
                    accept=".pdf,.doc,.docx,.ppt,.pptx,.txt"
                    onChange={handleFileChange}
                  />
                </label>
              </div>
              
              {selectedFile && (
                <div className="flex items-center p-2 mt-2 border rounded">
                  <FileText className="w-5 h-5 mr-2" />
                  <span className="text-sm">{selectedFile.name}</span>
                  <span className="ml-auto text-xs text-gray-500">
                    {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                  </span>
                </div>
              )}
              
              {uploadStatus === 'uploading' && (
                <div className="mt-4">
                  <div className="flex justify-between text-sm mb-1">
                    <span>Uploading...</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <Progress value={uploadProgress} className="w-full" />
                </div>
              )}
            </div>
          </CardContent>
          <CardFooter>
            <Button type="submit" className="w-full" disabled={isLoading || uploadStatus === 'uploading'}>
              {isLoading ? 'Uploading...' : 'Upload Module'}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}

export default UploadModule;
