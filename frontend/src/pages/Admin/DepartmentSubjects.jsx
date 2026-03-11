import React, { useEffect, useState } from 'react';
import { toast } from 'react-hot-toast';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import {
  BookOpen,
  Building2,
  Loader2,
  Pencil,
  Plus,
  Save,
  Trash2,
  X,
} from 'lucide-react';
import api from '../../utils/api';

function DepartmentSubjects() {
  const [departments, setDepartments] = useState([]);
  const [selectedDepartmentId, setSelectedDepartmentId] = useState('all');
  const [loading, setLoading] = useState(true);
  const [showDepartmentForm, setShowDepartmentForm] = useState(false);
  const [creatingDepartment, setCreatingDepartment] = useState(false);
  const [deletingSubjectId, setDeletingSubjectId] = useState(null);
  const [editingSubjectId, setEditingSubjectId] = useState(null);
  const [savingEdit, setSavingEdit] = useState(false);
  const [newDepartmentForm, setNewDepartmentForm] = useState({
    department_name: '',
    description: '',
  });
  const [globalSubjectForm, setGlobalSubjectForm] = useState({
    department_id: '',
    subject_name: '',
    description: '',
  });
  const [creatingGlobalSubject, setCreatingGlobalSubject] = useState(false);
  const [editForm, setEditForm] = useState({
    subject_name: '',
    description: '',
    department_id: null,
  });

  useEffect(() => {
    fetchDepartmentsSubjects();
  }, []);

  const fetchDepartmentsSubjects = async () => {
    try {
      setLoading(true);
      const response = await api.get('/admin/departments-subjects');
      const items = response.data?.departments || [];
      setDepartments(items);
      setSelectedDepartmentId((prev) => {
        if (prev === 'all') return prev;
        return items.some((department) => String(department.department_id) === String(prev))
          ? prev
          : 'all';
      });

      setGlobalSubjectForm((prev) => {
        const hasPrevDepartment = items.some(
          (department) => String(department.department_id) === String(prev.department_id)
        );
        if (hasPrevDepartment) return prev;
        if (selectedDepartmentId !== 'all') {
          return { ...prev, department_id: String(selectedDepartmentId) };
        }
        return { ...prev, department_id: items[0] ? String(items[0].department_id) : '' };
      });
    } catch (error) {
      console.error('Error fetching departments and subjects:', error);
      toast.error('Failed to load departments and subjects');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateSubjectFromDropdown = async () => {
    const selectedDepartment = Number(globalSubjectForm.department_id);
    const subjectName = (globalSubjectForm.subject_name || '').trim();
    if (!selectedDepartment) {
      toast.error('Please select a department');
      return;
    }
    if (!subjectName) {
      toast.error('Subject name is required');
      return;
    }

    try {
      setCreatingGlobalSubject(true);
      await api.post('/admin/subjects', {
        department_id: selectedDepartment,
        subject_name: subjectName,
        description: (globalSubjectForm.description || '').trim(),
      });
      toast.success('Subject added');
      setGlobalSubjectForm((prev) => ({
        ...prev,
        subject_name: '',
        description: '',
      }));
      await fetchDepartmentsSubjects();
    } catch (error) {
      toast.error(error.response?.data?.message || 'Failed to add subject');
    } finally {
      setCreatingGlobalSubject(false);
    }
  };

  const handleCreateDepartment = async () => {
    const departmentName = (newDepartmentForm.department_name || '').trim();
    if (!departmentName) {
      toast.error('Department name is required');
      return;
    }

    try {
      setCreatingDepartment(true);
      await api.post('/admin/departments', {
        department_name: departmentName,
        description: (newDepartmentForm.description || '').trim(),
      });
      toast.success('Department added');
      setNewDepartmentForm({ department_name: '', description: '' });
      setShowDepartmentForm(false);
      await fetchDepartmentsSubjects();
    } catch (error) {
      toast.error(error.response?.data?.message || 'Failed to add department');
    } finally {
      setCreatingDepartment(false);
    }
  };

  const startEditSubject = (subject) => {
    setEditingSubjectId(subject.subject_id);
    setEditForm({
      subject_name: subject.subject_name || '',
      description: subject.description || '',
      department_id: subject.department_id,
    });
  };

  const cancelEditSubject = () => {
    setEditingSubjectId(null);
    setEditForm({ subject_name: '', description: '', department_id: null });
  };

  const saveEditSubject = async (subjectId) => {
    if (!(editForm.subject_name || '').trim()) {
      toast.error('Subject name is required');
      return;
    }
    if (!editForm.department_id) {
      toast.error('Department is required');
      return;
    }

    try {
      setSavingEdit(true);
      await api.put(`/admin/subjects/${subjectId}`, {
        subject_name: editForm.subject_name.trim(),
        description: (editForm.description || '').trim(),
        department_id: editForm.department_id,
      });
      toast.success('Subject updated');
      cancelEditSubject();
      await fetchDepartmentsSubjects();
    } catch (error) {
      toast.error(error.response?.data?.message || 'Failed to update subject');
    } finally {
      setSavingEdit(false);
    }
  };

  const handleDeleteSubject = async (subjectId) => {
    if (!window.confirm('Delete this subject?')) return;

    try {
      setDeletingSubjectId(subjectId);
      await api.delete(`/admin/subjects/${subjectId}`);
      toast.success('Subject deleted');
      await fetchDepartmentsSubjects();
    } catch (error) {
      toast.error(error.response?.data?.message || 'Failed to delete subject');
    } finally {
      setDeletingSubjectId(null);
    }
  };

  const filteredDepartments =
    selectedDepartmentId === 'all'
      ? departments
      : departments.filter(
          (department) => String(department.department_id) === String(selectedDepartmentId)
        );

  const totalSubjects = departments.reduce(
    (sum, department) => sum + Number(department.subject_count || 0),
    0
  );

  const selectClass =
    'flex h-10 w-full rounded-md border border-amber-200 bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400';

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-500">
        <Loader2 className="h-5 w-5 animate-spin mr-2" />
        Loading departments and subjects...
      </div>
    );
  }

  return (
    <div className="w-full max-w-[1600px] mx-auto px-4 md:px-6 py-6 space-y-6">
      <div className="space-y-1">
        <h1 className="text-3xl font-bold tracking-tight text-gray-900">Departments & Subjects</h1>
        <p className="text-sm text-muted-foreground">
          Manage departments and subjects with a clean centralized view.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        <Card className="border border-amber-200 bg-white shadow-sm">
          <CardContent className="p-5">
            <p className="text-xs uppercase tracking-wide text-amber-700 font-semibold mb-1">
              Total Departments
            </p>
            <p className="text-3xl font-bold text-amber-900">{departments.length}</p>
          </CardContent>
        </Card>
        <Card className="border border-amber-200 bg-white shadow-sm">
          <CardContent className="p-5">
            <p className="text-xs uppercase tracking-wide text-amber-700 font-semibold mb-1">
              Total Subjects
            </p>
            <p className="text-3xl font-bold text-amber-900">{totalSubjects}</p>
          </CardContent>
        </Card>
        <Card className="border border-amber-200 bg-white shadow-sm">
          <CardContent className="p-5">
            <p className="text-xs uppercase tracking-wide text-amber-700 font-semibold mb-1">
              Showing
            </p>
            <p className="text-3xl font-bold text-amber-900">{filteredDepartments.length}</p>
            <p className="text-xs text-muted-foreground mt-1">department card(s)</p>
          </CardContent>
        </Card>
      </div>

      <Card className="border border-amber-200 bg-white shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-xl text-gray-900">Management Panel</CardTitle>
          <CardDescription>Filter departments and add new departments/subjects.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-3 items-end">
            <div className="space-y-2">
              <Label htmlFor="department-filter">Department Filter</Label>
              <select
                id="department-filter"
                className={selectClass}
                value={selectedDepartmentId}
                onChange={(e) => {
                  const nextDepartmentId = e.target.value;
                  setSelectedDepartmentId(nextDepartmentId);
                  if (nextDepartmentId !== 'all') {
                    setGlobalSubjectForm((prev) => ({
                      ...prev,
                      department_id: String(nextDepartmentId),
                    }));
                  }
                }}
              >
                <option value="all">All departments</option>
                {departments.map((department) => (
                  <option key={department.department_id} value={department.department_id}>
                    {department.department_name}
                  </option>
                ))}
              </select>
            </div>
            <Button
              type="button"
              variant={showDepartmentForm ? 'outline' : 'default'}
              onClick={() => setShowDepartmentForm((prev) => !prev)}
              disabled={creatingDepartment}
              className="border-amber-300"
            >
              <Plus className="h-4 w-4 mr-2" />
              {showDepartmentForm ? 'Cancel' : 'Add Department'}
            </Button>
          </div>

          {showDepartmentForm && (
            <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-4 space-y-3">
              <Label className="font-semibold text-amber-900">Create Department</Label>
              <Input
                placeholder="Department name"
                value={newDepartmentForm.department_name}
                onChange={(e) =>
                  setNewDepartmentForm((prev) => ({
                    ...prev,
                    department_name: e.target.value,
                  }))
                }
                disabled={creatingDepartment}
              />
              <Textarea
                rows={2}
                placeholder="Department description (optional)"
                value={newDepartmentForm.description}
                onChange={(e) =>
                  setNewDepartmentForm((prev) => ({ ...prev, description: e.target.value }))
                }
                disabled={creatingDepartment}
              />
              <Button onClick={handleCreateDepartment} disabled={creatingDepartment}>
                {creatingDepartment ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Plus className="h-4 w-4 mr-2" />
                )}
                Save Department
              </Button>
            </div>
          )}

          <div className="rounded-lg border border-amber-200 bg-amber-50/40 p-4 space-y-3">
            <Label className="font-semibold text-amber-900">Add Subject (Global)</Label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <select
                className={selectClass}
                value={globalSubjectForm.department_id}
                onChange={(e) =>
                  setGlobalSubjectForm((prev) => ({ ...prev, department_id: e.target.value }))
                }
                disabled={creatingGlobalSubject}
              >
                <option value="">Select department</option>
                {departments.map((department) => (
                  <option key={department.department_id} value={department.department_id}>
                    {department.department_name}
                  </option>
                ))}
              </select>
              <Input
                placeholder="Subject name"
                value={globalSubjectForm.subject_name}
                onChange={(e) =>
                  setGlobalSubjectForm((prev) => ({ ...prev, subject_name: e.target.value }))
                }
                disabled={creatingGlobalSubject}
              />
            </div>
            <Textarea
              rows={2}
              placeholder="Subject description (optional)"
              value={globalSubjectForm.description}
              onChange={(e) =>
                setGlobalSubjectForm((prev) => ({ ...prev, description: e.target.value }))
              }
              disabled={creatingGlobalSubject}
            />
            <Button onClick={handleCreateSubjectFromDropdown} disabled={creatingGlobalSubject}>
              {creatingGlobalSubject ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Plus className="h-4 w-4 mr-2" />
              )}
              Add Subject
            </Button>
          </div>
        </CardContent>
      </Card>

      {departments.length === 0 ? (
        <Card className="border border-amber-200 bg-white shadow-sm">
          <CardContent className="py-10 text-center text-gray-500">No departments found.</CardContent>
        </Card>
      ) : filteredDepartments.length === 0 ? (
        <Card className="border border-amber-200 bg-white shadow-sm">
          <CardContent className="py-10 text-center text-gray-500">
            No department matched the selected filter.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {filteredDepartments.map((department) => (
            <Card
              key={department.department_id}
              className="border border-amber-200 bg-white shadow-sm overflow-hidden"
            >
              <CardHeader className="pb-3 bg-amber-50/50 border-b border-amber-100">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <CardTitle className="flex items-center gap-2 text-gray-900">
                    <Building2 className="h-5 w-5 text-amber-700" />
                    {department.department_name}
                  </CardTitle>
                  <Badge className="bg-amber-100 text-amber-900 border border-amber-300">
                    {department.subject_count || 0} subject(s)
                  </Badge>
                </div>
                <CardDescription>
                  {department.description || 'No department description'}
                </CardDescription>
              </CardHeader>

              <CardContent className="space-y-4 pt-4">
                <div className="space-y-2">
                  {(department.subjects || []).length === 0 ? (
                    <p className="text-sm text-gray-500">No subjects yet.</p>
                  ) : (
                    department.subjects.map((subject) => (
                      <div
                        key={subject.subject_id}
                        className="rounded-lg border border-amber-100 bg-amber-50/30 p-3"
                      >
                        {editingSubjectId === subject.subject_id ? (
                          <div className="space-y-3">
                            <div className="space-y-1">
                              <Label>Subject Name</Label>
                              <Input
                                value={editForm.subject_name}
                                onChange={(e) =>
                                  setEditForm((prev) => ({
                                    ...prev,
                                    subject_name: e.target.value,
                                  }))
                                }
                                disabled={savingEdit}
                              />
                            </div>
                            <div className="space-y-1">
                              <Label>Department</Label>
                              <select
                                className={selectClass}
                                value={editForm.department_id == null ? '' : String(editForm.department_id)}
                                onChange={(e) =>
                                  setEditForm((prev) => ({
                                    ...prev,
                                    department_id: Number(e.target.value) || null,
                                  }))
                                }
                                disabled={savingEdit}
                              >
                                <option value="">Select department</option>
                                {departments.map((dept) => (
                                  <option key={dept.department_id} value={dept.department_id}>
                                    {dept.department_name}
                                  </option>
                                ))}
                              </select>
                            </div>
                            <div className="space-y-1">
                              <Label>Description</Label>
                              <Textarea
                                rows={2}
                                value={editForm.description}
                                onChange={(e) =>
                                  setEditForm((prev) => ({
                                    ...prev,
                                    description: e.target.value,
                                  }))
                                }
                                disabled={savingEdit}
                              />
                            </div>
                            <div className="flex gap-2 justify-end">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={cancelEditSubject}
                                disabled={savingEdit}
                              >
                                <X className="h-4 w-4 mr-1" />
                                Cancel
                              </Button>
                              <Button
                                size="sm"
                                onClick={() => saveEditSubject(subject.subject_id)}
                                disabled={savingEdit}
                              >
                                {savingEdit ? (
                                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                                ) : (
                                  <Save className="h-4 w-4 mr-1" />
                                )}
                                Save
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <div className="flex items-start justify-between gap-4">
                            <div>
                              <p className="font-medium text-gray-900 flex items-center gap-2">
                                <BookOpen className="h-4 w-4 text-amber-700" />
                                {subject.subject_name}
                              </p>
                              <p className="text-sm text-gray-500">
                                {subject.description || 'No description'}
                              </p>
                            </div>
                            <div className="flex gap-2 shrink-0">
                              <Button size="sm" variant="outline" onClick={() => startEditSubject(subject)}>
                                <Pencil className="h-4 w-4 mr-1" />
                                Edit
                              </Button>
                              <Button
                                size="sm"
                                variant="destructive"
                                onClick={() => handleDeleteSubject(subject.subject_id)}
                                disabled={deletingSubjectId === subject.subject_id}
                              >
                                {deletingSubjectId === subject.subject_id ? (
                                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                                ) : (
                                  <Trash2 className="h-4 w-4 mr-1" />
                                )}
                                Delete
                              </Button>
                            </div>
                          </div>
                        )}
                      </div>
                    ))
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

export default DepartmentSubjects;
