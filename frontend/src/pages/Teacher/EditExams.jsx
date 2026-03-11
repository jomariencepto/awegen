import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { useAuth } from '../../context/AuthContext';

import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '../../components/ui/card';
import { Textarea } from '../../components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';

import api from '../../utils/api';
import { toast } from 'react-hot-toast';
import { Loader2, Save, Eye, Edit3, ArrowLeft } from 'lucide-react';
import './css/TeacherDashboard.css';

function EditExam() {
  const { examId } = useParams();
  const navigate = useNavigate();
  const { currentUser } = useAuth();

  const [isLoading, setIsLoading] = useState(true);
  const [subjects, setSubjects] = useState([]);

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm({
    defaultValues: {
      title: '',
      description: '',
      category_id: '',
    },
  });

  const selectedCategoryId = watch('category_id');

  useEffect(() => {
    const fetchExamData = async () => {
      if (!currentUser?.user_id) {
        setIsLoading(false);
        return;
      }

      try {
        const [examRes, subjectRes] = await Promise.all([
          api.get(`/exams/${examId}`),
          api.get('/exams/categories'),
        ]);

        const examData = examRes.data?.exam || examRes.data || {};

        setSubjects(subjectRes.data.categories || []);
        setValue('title', examData.title || '');
        setValue('description', examData.description || '');
        setValue('category_id', examData.category_id ?? '');
      } catch (err) {
        console.error('Failed to load exam', err);
      }

      setIsLoading(false);
    };

    fetchExamData();
  }, [examId, currentUser?.user_id, setValue]);

  const onSubmit = async (data) => {
    setIsLoading(true);
    try {
      const payload = {
        title: data.title,
        description: data.description || '',
        category_id: Number(data.category_id),
      };

      await api.put(`/exams/${examId}`, payload);
      toast.success('Exam updated successfully!');
      setTimeout(() => {
        navigate('/teacher/manage-exams');
      }, 1000);
    } catch (err) {
      console.error('Update failed', err);
      toast.error(err.response?.data?.message || 'Failed to update exam');
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col justify-center items-center min-h-[400px]">
        <Loader2 className="h-12 w-12 animate-spin text-yellow-500 mb-4" />
        <p className="text-gray-600 font-medium">Loading exam details...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-yellow-50 rounded-lg">
            <Edit3 className="h-6 w-6 text-yellow-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Edit Exam</h1>
            <p className="text-sm text-gray-600 mt-0.5">
              Update exam title, description, and category
            </p>
          </div>
        </div>
        <Link to="/teacher/manage-exams">
          <Button
            variant="outline"
            className="border-gray-300 hover:border-yellow-500 hover:text-yellow-700 transition-colors"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Exams
          </Button>
        </Link>
      </div>

      <form onSubmit={handleSubmit(onSubmit)}>
        <input
          type="hidden"
          {...register('category_id', { required: 'Exam category is required' })}
        />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Exam Information</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label htmlFor="title" className="text-sm font-semibold text-gray-700">
                    Exam Title <span className="text-red-500">*</span>
                  </Label>
                  <Input
                    id="title"
                    {...register('title', { required: 'Title is required' })}
                    className={errors.title ? 'border-red-500 focus:ring-red-500' : ''}
                    placeholder="Enter exam title"
                  />
                  {errors.title && (
                    <p className="text-red-500 text-xs mt-1">{errors.title.message}</p>
                  )}
                </div>

                <div>
                  <Label htmlFor="description" className="text-sm font-semibold text-gray-700">
                    Description
                  </Label>
                  <Textarea
                    id="description"
                    {...register('description')}
                    placeholder="Provide a brief description of the exam"
                    rows={4}
                    className="resize-none"
                  />
                </div>

                <div>
                  <Label className="text-sm font-semibold text-gray-700">
                    Exam Category <span className="text-red-500">*</span>
                  </Label>
                  <Select
                    value={
                      selectedCategoryId === undefined ||
                      selectedCategoryId === null ||
                      selectedCategoryId === ''
                        ? undefined
                        : String(selectedCategoryId)
                    }
                    onValueChange={(v) =>
                      setValue('category_id', Number(v), {
                        shouldValidate: true,
                        shouldDirty: true,
                      })
                    }
                  >
                    <SelectTrigger
                      className={errors.category_id ? 'border-red-500 focus:ring-red-500' : ''}
                    >
                      <SelectValue placeholder="Select exam category" />
                    </SelectTrigger>
                    <SelectContent>
                      {subjects.map((s) => (
                        <SelectItem key={s.category_id} value={s.category_id.toString()}>
                          {s.category_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {errors.category_id && (
                    <p className="text-red-500 text-xs mt-1">{errors.category_id.message}</p>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Actions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Button
                  type="submit"
                  className="w-full bg-yellow-500 hover:bg-yellow-600 text-white font-semibold shadow-md hover:shadow-lg transition-all"
                  disabled={isLoading}
                >
                  <Save className="h-4 w-4 mr-2" />
                  {isLoading ? 'Saving...' : 'Save Changes'}
                </Button>

                <Link to={`/teacher/review-questions/${examId}`} className="block">
                  <Button
                    variant="outline"
                    className="w-full hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700 transition-colors justify-start"
                  >
                    <Edit3 className="h-4 w-4 mr-2" />
                    Edit Questions
                  </Button>
                </Link>

                <Link to={`/teacher/exam-preview/${examId}`} className="block">
                  <Button
                    variant="outline"
                    className="w-full hover:bg-green-50 hover:border-green-300 hover:text-green-700 transition-colors justify-start"
                  >
                    <Eye className="h-4 w-4 mr-2" />
                    Preview Exam
                  </Button>
                </Link>
              </CardContent>
            </Card>
          </div>
        </div>
      </form>
    </div>
  );
}

export default EditExam;
