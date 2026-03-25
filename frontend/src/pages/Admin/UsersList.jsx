import React, { useEffect, useMemo, useState } from 'react';
import { toast } from 'react-hot-toast';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Label } from '../../components/ui/label';
import { Checkbox } from '../../components/ui/checkbox';
import { Building2, Loader2, UserPlus, Users } from 'lucide-react';
import api from '../../utils/api';

const selectClassName =
  'flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-yellow-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50';

const initialCreateForm = {
  first_name: '',
  last_name: '',
  email: '',
  password: '',
  role: 'teacher',
  school_id_number: '',
  department_id: '',
  subject_ids: [],
  is_active: true,
};

const initialSubjectAssignmentState = {
  teacher: null,
  availableSubjects: [],
  selectedSubjectIds: [],
  departmentName: '',
  loading: false,
  saving: false,
};

function UsersList() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lookupLoading, setLookupLoading] = useState(true);
  const [creatingUser, setCreatingUser] = useState(false);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [schools, setSchools] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [createForm, setCreateForm] = useState(initialCreateForm);
  const [subjectAssignment, setSubjectAssignment] = useState(initialSubjectAssignmentState);

  const fetchUsers = async (nextPage = page) => {
    try {
      setLoading(true);
      const response = await api.get('/admin/users/all', {
        params: {
          page: nextPage,
          per_page: 20,
          search: search.trim() || undefined,
        },
      });
      setUsers(response.data?.users || []);
      setTotal(Number(response.data?.total) || 0);
      setPages(Math.max(1, Number(response.data?.pages) || 1));
      setPage(Number(response.data?.current_page) || nextPage);
    } catch (error) {
      console.error('Error fetching users:', error);
      setUsers([]);
      setTotal(0);
      setPages(1);
      setPage(1);
      toast.error('Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const fetchLookups = async () => {
    try {
      setLookupLoading(true);
      const [schoolsResponse, departmentsResponse] = await Promise.all([
        api.get('/users/schools'),
        api.get('/admin/departments-subjects'),
      ]);

      setSchools(schoolsResponse.data?.schools || []);
      setDepartments(departmentsResponse.data?.departments || []);
    } catch (error) {
      console.error('Error fetching admin lookup data:', error);
      setSchools([]);
      setDepartments([]);
      toast.error('Failed to load schools and departments');
    } finally {
      setLookupLoading(false);
    }
  };

  useEffect(() => {
    fetchLookups();
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchUsers(1);
    }, 250);

    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    if (!schools.length) return;

    setCreateForm((prev) => {
      const hasValidSchool = schools.some(
        (school) => String(school.school_id_number) === String(prev.school_id_number)
      );
      const nextSchoolId = hasValidSchool
        ? String(prev.school_id_number)
        : String(schools[0].school_id_number);
      const matchingDepartments = departments.filter(
        (department) => String(department.school_id_number) === nextSchoolId
      );
      const hasValidDepartment = matchingDepartments.some(
        (department) => String(department.department_id) === String(prev.department_id)
      );

      return {
        ...prev,
        school_id_number: nextSchoolId,
        department_id: hasValidDepartment
          ? String(prev.department_id)
          : matchingDepartments[0]
            ? String(matchingDepartments[0].department_id)
            : '',
      };
    });
  }, [schools, departments]);

  const filteredDepartments = useMemo(() => {
    if (!createForm.school_id_number) return departments;
    return departments.filter(
      (department) =>
        String(department.school_id_number) === String(createForm.school_id_number)
    );
  }, [departments, createForm.school_id_number]);

  const selectedCreateDepartment = useMemo(
    () =>
      filteredDepartments.find(
        (department) => String(department.department_id) === String(createForm.department_id)
      ) || null,
    [filteredDepartments, createForm.department_id]
  );

  const createAvailableSubjects = useMemo(
    () =>
      departments
        .flatMap((department) =>
          (department.subjects || []).map((subject) => ({
            ...subject,
            department_name: department.department_name,
          }))
        )
        .sort((a, b) => {
          const departmentComparison = String(a.department_name || '').localeCompare(
            String(b.department_name || '')
          );
          if (departmentComparison !== 0) return departmentComparison;
          return String(a.subject_name || '').localeCompare(String(b.subject_name || ''));
        }),
    [departments]
  );

  useEffect(() => {
    const allowedSubjectIds = new Set(
      createAvailableSubjects.map((subject) => Number(subject.subject_id))
    );

    setCreateForm((prev) => {
      const nextSubjectIds = (prev.subject_ids || []).filter((subjectId) =>
        allowedSubjectIds.has(Number(subjectId))
      );

      if (
        nextSubjectIds.length === (prev.subject_ids || []).length &&
        nextSubjectIds.every((subjectId, index) => Number(subjectId) === Number(prev.subject_ids[index]))
      ) {
        return prev;
      }

      return {
        ...prev,
        subject_ids: nextSubjectIds,
      };
    });
  }, [createAvailableSubjects]);

  const searchedUsers = users;

  const normalizeRole = (role) => String(role || '').toLowerCase();
  const isTeacherUser = (user) => normalizeRole(user.role) === 'teacher';
  const isDepartmentUser = (user) =>
    ['department_head', 'department'].includes(normalizeRole(user.role));

  const teacherUsers = useMemo(
    () => searchedUsers.filter((user) => isTeacherUser(user)),
    [searchedUsers]
  );
  const departmentUsers = useMemo(
    () => searchedUsers.filter((user) => isDepartmentUser(user)),
    [searchedUsers]
  );
  const otherUsers = useMemo(
    () =>
      searchedUsers.filter((user) => !isTeacherUser(user) && !isDepartmentUser(user)),
    [searchedUsers]
  );

  const formatRole = (role) => {
    if (!role) return 'N/A';
    return String(role).replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
  };

  const formatName = (user) => {
    const fullName = `${user.first_name || ''} ${user.last_name || ''}`.trim();
    return fullName || user.username || 'N/A';
  };

  const isTeacherCreateForm = normalizeRole(createForm.role) === 'teacher';
  const createAccountDescription = isTeacherCreateForm
    ? 'Accounts created here are verified immediately. If you keep approval checked, the teacher can log in right away. If you uncheck it, the teacher stays active but must be approved first by the selected department.'
    : 'Department head accounts created here are verified immediately. If you uncheck the box, the account will be created as inactive until an authorized user activates it.';
  const createAccountToggleLabel = isTeacherCreateForm
    ? 'Approve immediately'
    : 'Create as active account';
  const createAccountToggleHelp = isTeacherCreateForm
    ? (
      createForm.is_active
        ? 'Checked: the teacher will be approved and can log in immediately.'
        : 'Unchecked: the teacher will appear as pending approval for the selected department before first login.'
    )
    : (
      createForm.is_active
        ? 'Checked: the department head can log in immediately.'
        : 'Unchecked: the department head account will be inactive until it is activated later.'
    );

  const openSubjectAssignment = async (teacher) => {
    if (!teacher?.user_id) return;

    setSubjectAssignment((prev) => ({
      ...prev,
      teacher,
      availableSubjects: [],
      selectedSubjectIds: [],
      departmentName: teacher.department_name || '',
      loading: true,
      saving: false,
    }));

    try {
      const response = await api.get(`/admin/teachers/${teacher.user_id}/subjects`);
      setSubjectAssignment({
        teacher: response.data?.teacher || teacher,
        availableSubjects: response.data?.available_subjects || [],
        selectedSubjectIds: response.data?.assigned_subject_ids || [],
        departmentName:
          response.data?.department_name || response.data?.teacher?.department_name || '',
        loading: false,
        saving: false,
      });
    } catch (error) {
      console.error('Error loading teacher subjects:', error);
      setSubjectAssignment(initialSubjectAssignmentState);
      toast.error(error.response?.data?.message || 'Failed to load teacher subjects');
    }
  };

  const closeSubjectAssignment = () => {
    setSubjectAssignment(initialSubjectAssignmentState);
  };

  const toggleSubjectSelection = (subjectId, checked) => {
    setSubjectAssignment((prev) => {
      const selectedSubjectIds = new Set(prev.selectedSubjectIds || []);
      if (checked) {
        selectedSubjectIds.add(Number(subjectId));
      } else {
        selectedSubjectIds.delete(Number(subjectId));
      }

      return {
        ...prev,
        selectedSubjectIds: Array.from(selectedSubjectIds).sort((a, b) => a - b),
      };
    });
  };

  const toggleCreateSubjectSelection = (subjectId, checked) => {
    setCreateForm((prev) => {
      const selectedSubjectIds = new Set((prev.subject_ids || []).map((value) => Number(value)));
      if (checked) {
        selectedSubjectIds.add(Number(subjectId));
      } else {
        selectedSubjectIds.delete(Number(subjectId));
      }

      return {
        ...prev,
        subject_ids: Array.from(selectedSubjectIds).sort((a, b) => a - b),
      };
    });
  };

  const handleSaveSubjectAssignments = async () => {
    if (!subjectAssignment.teacher?.user_id) return;

    try {
      setSubjectAssignment((prev) => ({ ...prev, saving: true }));
      const response = await api.put(`/admin/teachers/${subjectAssignment.teacher.user_id}/subjects`, {
        subject_ids: subjectAssignment.selectedSubjectIds,
      });

      setSubjectAssignment((prev) => ({
        ...prev,
        teacher: response.data?.teacher || prev.teacher,
        availableSubjects: response.data?.available_subjects || prev.availableSubjects,
        selectedSubjectIds: response.data?.assigned_subject_ids || prev.selectedSubjectIds,
        departmentName:
          response.data?.department_name || response.data?.teacher?.department_name || prev.departmentName,
        saving: false,
        loading: false,
      }));
      toast.success(response.data?.message || 'Teacher subjects updated');
      await fetchUsers(page);
    } catch (error) {
      console.error('Error saving teacher subjects:', error);
      setSubjectAssignment((prev) => ({ ...prev, saving: false }));
      toast.error(error.response?.data?.message || 'Failed to save teacher subjects');
    }
  };

  const handleSchoolChange = (value) => {
    const nextDepartments = departments.filter(
      (department) => String(department.school_id_number) === String(value)
    );

    setCreateForm((prev) => ({
      ...prev,
      school_id_number: value,
      department_id: nextDepartments[0] ? String(nextDepartments[0].department_id) : '',
      subject_ids: [],
    }));
  };

  const handleCreateUser = async () => {
    const payload = {
      ...createForm,
      first_name: createForm.first_name.trim(),
      last_name: createForm.last_name.trim(),
      email: createForm.email.trim(),
      password: createForm.password,
      school_id_number: Number(createForm.school_id_number),
      department_id: Number(createForm.department_id),
      subject_ids:
        normalizeRole(createForm.role) === 'teacher'
          ? (createForm.subject_ids || []).map((subjectId) => Number(subjectId))
          : [],
      is_active: Boolean(createForm.is_active),
    };

    if (!payload.first_name || !payload.last_name || !payload.email || !payload.password) {
      toast.error('Please complete all required fields');
      return;
    }

    if (!payload.school_id_number || !payload.department_id) {
      toast.error('School and department are required');
      return;
    }

    if (normalizeRole(payload.role) === 'teacher' && payload.subject_ids.length === 0) {
      toast.error('Please choose at least one subject for this teacher');
      return;
    }

    try {
      setCreatingUser(true);
      const response = await api.post('/admin/users', payload);
      toast.success(response.data?.message || 'User account created');
      const createdUser = response.data?.user || null;

      setCreateForm((prev) => ({
        ...prev,
        first_name: '',
        last_name: '',
        email: '',
        password: '',
        subject_ids: [],
        is_active: true,
      }));

      await fetchUsers(1);
    } catch (error) {
      console.error('Error creating user account:', error);
      toast.error(error.response?.data?.message || 'Failed to create user account');
    } finally {
      setCreatingUser(false);
    }
  };

  const renderUsersTable = (rows, emptyMessage, options = {}) => {
    const showSubjectActions = Boolean(options.showSubjectActions);

    if (rows.length === 0) {
      return <p className="py-6 text-center text-sm text-muted-foreground">{emptyMessage}</p>;
    }

    return (
      <div className="overflow-x-auto rounded-lg border border-amber-100">
        <table className="w-full text-sm">
          <thead className="bg-amber-50/70">
            <tr className="text-left">
              <th className="px-4 py-3 font-semibold text-gray-800">Name</th>
              <th className="px-4 py-3 font-semibold text-gray-800">Email</th>
              <th className="px-4 py-3 font-semibold text-gray-800">Role</th>
              <th className="px-4 py-3 font-semibold text-gray-800">Department</th>
              <th className="px-4 py-3 font-semibold text-gray-800">Status</th>
              {showSubjectActions && (
                <th className="px-4 py-3 font-semibold text-gray-800 text-right">Actions</th>
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((user) => (
              <tr key={user.user_id} className="border-t border-amber-100 hover:bg-amber-50/40">
                <td className="px-4 py-3 font-medium text-gray-900">{formatName(user)}</td>
                <td className="px-4 py-3 text-gray-700">{user.email || 'N/A'}</td>
                <td className="px-4 py-3 text-gray-700">{formatRole(user.role)}</td>
                <td className="px-4 py-3 text-gray-700">{user.department_name || 'N/A'}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-2">
                    {user.is_approved ? (
                      <Badge className="border border-emerald-300 bg-emerald-100 text-emerald-800">
                        Approved
                      </Badge>
                    ) : (
                      <Badge className="border border-amber-300 bg-amber-100 text-amber-900">
                        Pending Approval
                      </Badge>
                    )}
                    {user.is_active ? (
                      <Badge className="border border-sky-300 bg-sky-100 text-sky-800">
                        Active
                      </Badge>
                    ) : (
                      <Badge className="border border-slate-300 bg-slate-100 text-slate-700">
                        Inactive
                      </Badge>
                    )}
                  </div>
                </td>
                {showSubjectActions && (
                  <td className="px-4 py-3 text-right">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => openSubjectAssignment(user)}
                    >
                      {subjectAssignment.teacher?.user_id === user.user_id ? 'Manage Subjects' : 'Assign Subjects'}
                    </Button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 px-4 py-6 md:px-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">Users</h1>
        </div>
        <div className="grid min-w-[220px] grid-cols-1 gap-3 sm:grid-cols-3">
          <Card className="border border-amber-200 bg-white shadow-sm">
            <CardContent className="p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Total</p>
              <p className="mt-1 text-2xl font-bold text-amber-900">{total}</p>
            </CardContent>
          </Card>
          <Card className="border border-amber-200 bg-white shadow-sm">
            <CardContent className="p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">
                Teachers
              </p>
              <p className="mt-1 text-2xl font-bold text-amber-900">{teacherUsers.length}</p>
            </CardContent>
          </Card>
          <Card className="border border-amber-200 bg-white shadow-sm">
            <CardContent className="p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">
                Department
              </p>
              <p className="mt-1 text-2xl font-bold text-amber-900">{departmentUsers.length}</p>
            </CardContent>
          </Card>
        </div>
      </div>

      <Card className="border border-amber-200 bg-white shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-xl text-gray-900">
            <UserPlus className="h-5 w-5 text-amber-700" />
            Create Account
          </CardTitle>
          <CardDescription>
            {createAccountDescription}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="role">Account Type</Label>
              <select
                id="role"
                className={selectClassName}
                value={createForm.role}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, role: e.target.value }))
                }
                disabled={creatingUser || lookupLoading}
              >
                <option value="teacher">Teacher</option>
                <option value="department_head">Department Head</option>
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="school">School</Label>
              <select
                id="school"
                className={selectClassName}
                value={createForm.school_id_number}
                onChange={(e) => handleSchoolChange(e.target.value)}
                disabled={creatingUser || lookupLoading || schools.length === 0}
              >
                {schools.length === 0 ? (
                  <option value="">No schools available</option>
                ) : (
                  schools.map((school) => (
                    <option key={school.school_id_number} value={school.school_id_number}>
                      {school.school_name}
                    </option>
                  ))
                )}
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="department">Department</Label>
              <select
                id="department"
                className={selectClassName}
                value={createForm.department_id}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, department_id: e.target.value }))
                }
                disabled={creatingUser || lookupLoading || filteredDepartments.length === 0}
              >
                {filteredDepartments.length === 0 ? (
                  <option value="">No departments available</option>
                ) : (
                  filteredDepartments.map((department) => (
                    <option key={department.department_id} value={department.department_id}>
                      {department.department_name}
                    </option>
                  ))
                )}
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="first_name">First Name</Label>
              <Input
                id="first_name"
                value={createForm.first_name}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, first_name: e.target.value }))
                }
                placeholder="Juan"
                disabled={creatingUser}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="last_name">Last Name</Label>
              <Input
                id="last_name"
                value={createForm.last_name}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, last_name: e.target.value }))
                }
                placeholder="Dela Cruz"
                disabled={creatingUser}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={createForm.email}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, email: e.target.value }))
                }
                placeholder="teacher@example.com"
                disabled={creatingUser}
              />
            </div>

            <div className="space-y-2 xl:col-span-2">
              <Label htmlFor="password">Initial Password</Label>
              <Input
                id="password"
                type="text"
                value={createForm.password}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, password: e.target.value }))
                }
                placeholder="Set a strong password"
                disabled={creatingUser}
              />
              <p className="text-xs text-muted-foreground">
                Use 8+ characters with uppercase, lowercase, number, and special character.
              </p>
              <p className="text-xs text-amber-800">
                {createAccountToggleHelp}
              </p>
            </div>

            <div className="flex items-end">
              <label className="flex items-center gap-3 rounded-md border border-amber-200 bg-amber-50/50 px-3 py-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={createForm.is_active}
                  onChange={(e) =>
                    setCreateForm((prev) => ({ ...prev, is_active: e.target.checked }))
                  }
                    disabled={creatingUser}
                  />
                {createAccountToggleLabel}
              </label>
            </div>
          </div>

          {normalizeRole(createForm.role) === 'teacher' && (
            <div className="space-y-3 rounded-lg border border-amber-200 bg-amber-50/30 px-4 py-4">
              <div>
                <p className="text-sm font-semibold text-gray-900">Assign Subjects Before Creating</p>
                <p className="text-xs text-muted-foreground">
                  The teacher will only see these assigned subjects in Upload Module and Create
                  Exam, even if the subject is outside the teacher&apos;s department.
                </p>
              </div>

              {createAvailableSubjects.length === 0 ? (
                <div className="rounded-md border border-amber-100 bg-white px-4 py-3 text-sm text-gray-700">
                  No subjects are available yet. Create subjects first before creating this teacher
                  account.
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {createAvailableSubjects.map((subject) => (
                    <label
                      key={subject.subject_id}
                      className="flex cursor-pointer items-start gap-3 rounded-lg border border-amber-100 bg-white px-4 py-3 hover:bg-amber-50/40"
                    >
                      <Checkbox
                        checked={(createForm.subject_ids || []).includes(subject.subject_id)}
                        onCheckedChange={(checked) =>
                          toggleCreateSubjectSelection(subject.subject_id, checked === true)
                        }
                        disabled={creatingUser}
                      />
                      <div>
                        <p className="font-medium text-gray-900">{subject.subject_name}</p>
                        <p className="text-xs text-muted-foreground">
                          {subject.department_name || selectedCreateDepartment?.department_name || 'Department subject'}
                        </p>
                      </div>
                    </label>
                  ))}
                </div>
              )}

              <div className="text-xs text-amber-800">
                Selected: {(createForm.subject_ids || []).length} subject(s)
              </div>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-100 bg-amber-50/40 px-4 py-3">
            <Button
              type="button"
              onClick={handleCreateUser}
              disabled={
                creatingUser ||
                lookupLoading ||
                schools.length === 0 ||
                filteredDepartments.length === 0 ||
                (normalizeRole(createForm.role) === 'teacher' &&
                  (createForm.subject_ids || []).length === 0)
              }
            >
              {creatingUser ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <UserPlus className="mr-2 h-4 w-4" />
              )}
              Create Account
            </Button>
          </div>
        </CardContent>
      </Card>

      {subjectAssignment.teacher && (
        <Card className="border border-amber-200 bg-white shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-xl text-gray-900">Assign Teacher Subjects</CardTitle>
            <CardDescription>
              Admin controls which subjects this teacher can use in Upload Module and Create Exam
              across all departments.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <div className="rounded-lg border border-amber-100 bg-amber-50/40 px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Teacher</p>
                <p className="mt-1 font-semibold text-gray-900">{formatName(subjectAssignment.teacher)}</p>
                <p className="text-sm text-gray-600">{subjectAssignment.teacher.email || 'No email'}</p>
              </div>
              <div className="rounded-lg border border-amber-100 bg-amber-50/40 px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Department</p>
                <p className="mt-1 font-semibold text-gray-900">
                  {subjectAssignment.departmentName || subjectAssignment.teacher.department_name || 'No department'}
                </p>
              </div>
              <div className="rounded-lg border border-amber-100 bg-amber-50/40 px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Assigned</p>
                <p className="mt-1 font-semibold text-gray-900">
                  {subjectAssignment.selectedSubjectIds.length} subject(s)
                </p>
              </div>
            </div>

            {subjectAssignment.loading ? (
              <div className="flex items-center justify-center py-10 text-muted-foreground">
                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                Loading teacher subjects...
              </div>
            ) : subjectAssignment.availableSubjects.length === 0 ? (
              <div className="rounded-lg border border-amber-100 bg-amber-50/40 px-4 py-4 text-sm text-gray-700">
                No subjects are available yet. Create subjects first, then come back here to assign
                them.
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                {subjectAssignment.availableSubjects.map((subject) => (
                  <label
                    key={subject.subject_id}
                    className="flex cursor-pointer items-start gap-3 rounded-lg border border-amber-100 bg-white px-4 py-3 hover:bg-amber-50/40"
                  >
                    <Checkbox
                      checked={subjectAssignment.selectedSubjectIds.includes(subject.subject_id)}
                      onCheckedChange={(checked) => toggleSubjectSelection(subject.subject_id, checked === true)}
                      disabled={subjectAssignment.saving}
                    />
                    <div>
                      <p className="font-medium text-gray-900">{subject.subject_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {subject.department_name || subjectAssignment.departmentName || 'Department subject'}
                      </p>
                    </div>
                  </label>
                ))}
              </div>
            )}

            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-100 bg-amber-50/40 px-4 py-3">
              <div className="text-sm text-gray-700">
                Selected subjects are the only ones this teacher will see for uploads and exam creation.
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() =>
                    setSubjectAssignment((prev) => ({ ...prev, selectedSubjectIds: [] }))
                  }
                  disabled={subjectAssignment.loading || subjectAssignment.saving}
                >
                  Clear
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={closeSubjectAssignment}
                  disabled={subjectAssignment.saving}
                >
                  Close
                </Button>
                <Button
                  type="button"
                  onClick={handleSaveSubjectAssignments}
                  disabled={subjectAssignment.loading || subjectAssignment.saving}
                >
                  {subjectAssignment.saving ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : null}
                  Save Subjects
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <Card className="border border-amber-200 bg-white shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-xl text-gray-900">Users Directory</CardTitle>
          <CardDescription>
            View all existing user accounts, grouped by role.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="relative max-w-md">
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search users..."
              className="pl-3"
            />
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Loading users...
            </div>
          ) : searchedUsers.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              <Users className="mx-auto mb-3 h-10 w-10 text-amber-300" />
              No users found for this page or filter.
            </div>
          ) : (
            <div className="space-y-5">
              <div className="space-y-2">
                <p className="text-sm font-semibold text-gray-900">Teacher Accounts</p>
                {renderUsersTable(teacherUsers, 'No teacher account on this page or filter.', {
                  showSubjectActions: true,
                })}
              </div>

              <div className="space-y-2">
                <p className="flex items-center gap-2 text-sm font-semibold text-gray-900">
                  <Building2 className="h-4 w-4 text-amber-700" />
                  Department Accounts
                </p>
                {renderUsersTable(
                  departmentUsers,
                  'No department account on this page or filter.'
                )}
              </div>

              <div className="space-y-2">
                <p className="text-sm font-semibold text-gray-900">Other Accounts</p>
                {renderUsersTable(otherUsers, 'No other account on this page or filter.')}
              </div>
            </div>
          )}

          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              Page {page} of {pages}
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={() => fetchUsers(page - 1)}
                disabled={loading || page <= 1}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                onClick={() => fetchUsers(page + 1)}
                disabled={loading || page >= pages}
              >
                Next
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default UsersList;
