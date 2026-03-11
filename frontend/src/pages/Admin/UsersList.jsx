import React, { useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Building2, Loader2, Search, Users } from 'lucide-react';
import api from '../../utils/api';

function UsersList() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');

  const fetchUsers = async (nextPage = page) => {
    try {
      setLoading(true);
      const response = await api.get('/admin/users/all', {
        params: { page: nextPage, per_page: 20 },
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
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers(1);
  }, []);

  const searchedUsers = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) return users;
    return users.filter((user) => {
      const fullName = `${user.first_name || ''} ${user.last_name || ''}`.trim().toLowerCase();
      return (
        fullName.includes(keyword) ||
        (user.email || '').toLowerCase().includes(keyword) ||
        (user.role || '').toLowerCase().includes(keyword) ||
        (user.department_name || '').toLowerCase().includes(keyword)
      );
    });
  }, [users, search]);

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
    return String(role).replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  };

  const formatName = (user) => {
    const fullName = `${user.first_name || ''} ${user.last_name || ''}`.trim();
    return fullName || user.username || 'N/A';
  };

  const renderUsersTable = (rows, emptyMessage) => {
    if (rows.length === 0) {
      return <p className="text-sm text-muted-foreground py-6 text-center">{emptyMessage}</p>;
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
                  {user.is_approved ? (
                    <Badge className="bg-emerald-100 text-emerald-800 border border-emerald-300">
                      Approved
                    </Badge>
                  ) : (
                    <Badge className="bg-amber-100 text-amber-900 border border-amber-300">
                      Pending
                    </Badge>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="w-full max-w-[1600px] mx-auto px-4 md:px-6 py-6 space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">All Users</h1>
          <p className="text-sm text-muted-foreground mt-1">
            View all user accounts including assigned departments.
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 min-w-[220px]">
          <Card className="border border-amber-200 bg-white shadow-sm">
            <CardContent className="p-4">
              <p className="text-xs uppercase tracking-wide text-amber-700 font-semibold">Total</p>
              <p className="text-2xl font-bold text-amber-900 mt-1">{total}</p>
            </CardContent>
          </Card>
          <Card className="border border-amber-200 bg-white shadow-sm">
            <CardContent className="p-4">
              <p className="text-xs uppercase tracking-wide text-amber-700 font-semibold">Teachers</p>
              <p className="text-2xl font-bold text-amber-900 mt-1">{teacherUsers.length}</p>
            </CardContent>
          </Card>
          <Card className="border border-amber-200 bg-white shadow-sm">
            <CardContent className="p-4">
              <p className="text-xs uppercase tracking-wide text-amber-700 font-semibold">Department</p>
              <p className="text-2xl font-bold text-amber-900 mt-1">{departmentUsers.length}</p>
            </CardContent>
          </Card>
        </div>
      </div>

      <Card className="border border-amber-200 bg-white shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-xl text-gray-900">Users Directory</CardTitle>
          <CardDescription>
            Separated view for Teacher and Department accounts.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="relative max-w-md">
            {/* <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /> */}
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search users..."
              className="pl-9"
            />
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin mr-2" />
              Loading users...
            </div>
          ) : searchedUsers.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Users className="h-10 w-10 mx-auto mb-3 text-amber-300" />
              No users found for this page/filter.
            </div>
          ) : (
            <div className="space-y-5">
              <div className="space-y-2">
                <p className="text-sm font-semibold text-gray-900">Teacher Accounts</p>
                {renderUsersTable(teacherUsers, 'No teacher account on this page/filter.')}
              </div>

              <div className="space-y-2">
                <p className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                  <Building2 className="h-4 w-4 text-amber-700" />
                  Department Accounts
                </p>
                {renderUsersTable(departmentUsers, 'No department account on this page/filter.')}
              </div>

              <div className="space-y-2">
                <p className="text-sm font-semibold text-gray-900">Other Accounts</p>
                {renderUsersTable(otherUsers, 'No other account on this page/filter.')}
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
