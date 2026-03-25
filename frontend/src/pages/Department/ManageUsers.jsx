import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import api from '../../utils/api';

function ManageUsers() {
  const [users, setUsers] = useState([]);
  const [filteredUsers, setFilteredUsers] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  const sortUsersByNewestFirst = (userList = []) =>
    [...userList].sort((left, right) => {
      const leftCreatedAt = left?.created_at ? new Date(left.created_at).getTime() : 0;
      const rightCreatedAt = right?.created_at ? new Date(right.created_at).getTime() : 0;

      if (rightCreatedAt !== leftCreatedAt) {
        return rightCreatedAt - leftCreatedAt;
      }

      return (right?.user_id || 0) - (left?.user_id || 0);
    });

  useEffect(() => {
    fetchUsers();
  }, []);

  useEffect(() => {
    if (searchTerm) {
      setFilteredUsers(sortUsersByNewestFirst(users.filter(user =>
        user.first_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        user.last_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        user.email.toLowerCase().includes(searchTerm.toLowerCase())
      )));
    } else {
      setFilteredUsers(sortUsersByNewestFirst(users));
    }
  }, [searchTerm, users]);

  const fetchUsers = async () => {
    try {
      const response = await api.get('/departments/users/department/teachers', {
        params: {
          page: 1,
          per_page: 1000, // fetch up to 1000 in one go; adjust if needed
        },
      });
      const sortedUsers = sortUsersByNewestFirst(response.data.users || []);
      setUsers(sortedUsers);
      setFilteredUsers(sortedUsers);
    } catch (error) {
      console.error('Error fetching users:', error);
      setUsers([]);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleUserStatus = async (userId, currentStatus) => {
    try {
      await api.put(`/users/${userId}`, { is_active: !currentStatus });
      
      setUsers(users.map(user => 
        user.user_id === userId 
          ? { ...user, is_active: !currentStatus }
          : user
      ));
    } catch (error) {
      console.error('Error updating user status:', error);
    }
  };

  const approveUser = async (userId, approve = true) => {
    try {
      await api.post('/users/approve', { user_id: userId, is_approved: approve });
      setUsers(users.map(user =>
        user.user_id === userId
          ? { ...user, is_approved: approve }
          : user
      ));
    } catch (error) {
      console.error('Error updating user approval:', error);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading users...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Manage Users</h1>
        <p className="mt-1 text-sm text-gray-600">
          Manage teachers in your department
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Search Users</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="search">Search by name or email</Label>
            <Input
              id="search"
              placeholder="Search users..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      {filteredUsers.length === 0 ? (
        <Card>
          <CardContent className="pt-6">
            <div className="text-center py-12">
              <div className="text-gray-400 text-5xl mb-4">👥</div>
              <h3 className="text-lg font-medium text-gray-900 mb-1">No users found</h3>
              <p className="text-gray-500">
                {searchTerm ? 'Try adjusting your search' : 'No teachers in your department yet'}
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Department Teachers</CardTitle>
            <CardDescription>
              {filteredUsers.length} {filteredUsers.length === 1 ? 'teacher' : 'teachers'} found
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Name
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Email
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Approval
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Joined
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredUsers.map((user) => (
                    <tr key={user.user_id}>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">
                          {user.first_name} {user.last_name}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-500">{user.email}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <Badge variant={user.is_active ? 'default' : 'secondary'}>
                          {user.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <Badge variant={user.is_approved ? 'default' : 'destructive'}>
                          {user.is_approved ? 'Approved' : 'Pending'}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(user.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm space-x-2">
                        <Button
                          size="sm"
                          variant={user.is_active ? 'destructive' : 'default'}
                          onClick={() => toggleUserStatus(user.user_id, user.is_active)}
                        >
                          {user.is_active ? 'Deactivate' : 'Activate'}
                        </Button>
                        {!user.is_approved ? (
                          <Button
                            size="sm"
                            variant="default"
                            onClick={() => approveUser(user.user_id, true)}
                          >
                            Approve
                          </Button>
                        ) : (
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => approveUser(user.user_id, false)}
                          >
                            Revoke
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default ManageUsers;
