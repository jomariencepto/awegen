import React, { useEffect, useState } from 'react';
import { toast } from 'react-hot-toast';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import api from '../../utils/api';

const formatRole = (role) => {
  if (!role) return 'N/A';
  return String(role)
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

function Settings() {
  const { currentUser, refreshCurrentUser } = useAuth();
  const [isProfileLoading, setIsProfileLoading] = useState(false);
  const [isPasswordLoading, setIsPasswordLoading] = useState(false);
  const [emailChangePassword, setEmailChangePassword] = useState('');

  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    email: '',
  });

  const [passwordData, setPasswordData] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });

  useEffect(() => {
    setFormData({
      first_name: currentUser?.first_name || '',
      last_name: currentUser?.last_name || '',
      email: currentUser?.email || '',
    });
    setEmailChangePassword('');
  }, [currentUser]);

  const normalizedCurrentEmail = String(currentUser?.email || '').trim().toLowerCase();
  const normalizedFormEmail = String(formData.email || '').trim().toLowerCase();
  const isEmailChanged = normalizedFormEmail !== normalizedCurrentEmail;
  const departmentLabel =
    currentUser?.department?.department_name ||
    currentUser?.department_name ||
    'N/A';

  const handleProfileUpdate = async (e) => {
    e.preventDefault();

    const firstName = formData.first_name.trim();
    const lastName = formData.last_name.trim();
    const email = formData.email.trim();

    if (!firstName || !lastName || !email) {
      toast.error('First name, last name, and email are required');
      return;
    }

    if (isEmailChanged && !emailChangePassword) {
      toast.error('Current password is required to change your email');
      return;
    }

    setIsProfileLoading(true);

    try {
      const response = await api.put('/users/me', {
        first_name: firstName,
        last_name: lastName,
        email,
        current_password: isEmailChanged ? emailChangePassword : '',
      });

      const updatedUser = response.data?.user || {};
      const cachedUser = JSON.parse(localStorage.getItem('user') || 'null');
      if (cachedUser) {
        localStorage.setItem(
          'user',
          JSON.stringify({
            ...cachedUser,
            ...updatedUser,
            first_name: updatedUser.first_name || firstName,
            last_name: updatedUser.last_name || lastName,
            email: updatedUser.email || email,
          })
        );
      }

      await refreshCurrentUser();
      setEmailChangePassword('');
      toast.success(response.data?.message || 'Profile updated successfully');
    } catch (error) {
      const message = error.response?.data?.message || 'Failed to update profile';
      toast.error(message);
    } finally {
      setIsProfileLoading(false);
    }
  };

  const handlePasswordChange = async (e) => {
    e.preventDefault();

    if (passwordData.new_password !== passwordData.confirm_password) {
      toast.error('New passwords do not match');
      return;
    }

    setIsPasswordLoading(true);

    try {
      await api.put('/users/change-password', {
        current_password: passwordData.current_password,
        new_password: passwordData.new_password,
      });
      toast.success('Password changed successfully');
      setPasswordData({
        current_password: '',
        new_password: '',
        confirm_password: '',
      });
    } catch (error) {
      const message = error.response?.data?.message || 'Failed to change password';
      toast.error(message);
    } finally {
      setIsPasswordLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="mt-1 text-sm text-gray-600">
          Manage your account settings and preferences
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Profile Information</CardTitle>
            <CardDescription>
              Update your personal information
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleProfileUpdate} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="first_name">First Name</Label>
                <Input
                  id="first_name"
                  value={formData.first_name}
                  onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="last_name">Last Name</Label>
                <Input
                  id="last_name"
                  value={formData.last_name}
                  onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  required
                />
                <p className="text-xs text-gray-500">
                  You can change your email here. If you update it, enter your current password below and AWEGen will send a confirmation email to the new address.
                </p>
              </div>

              {isEmailChanged && (
                <div className="space-y-2">
                  <Label htmlFor="email_change_password">Current Password</Label>
                  <Input
                    id="email_change_password"
                    type="password"
                    value={emailChangePassword}
                    onChange={(e) => setEmailChangePassword(e.target.value)}
                    placeholder="Required to confirm your new email"
                    required={isEmailChanged}
                  />
                </div>
              )}

              <Button type="submit" disabled={isProfileLoading}>
                {isProfileLoading ? 'Updating...' : 'Update Profile'}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Change Password</CardTitle>
            <CardDescription>
              Update your password to keep your account secure
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handlePasswordChange} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="current_password">Current Password</Label>
                <Input
                  id="current_password"
                  type="password"
                  value={passwordData.current_password}
                  onChange={(e) => setPasswordData({ ...passwordData, current_password: e.target.value })}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="new_password">New Password</Label>
                <Input
                  id="new_password"
                  type="password"
                  value={passwordData.new_password}
                  onChange={(e) => setPasswordData({ ...passwordData, new_password: e.target.value })}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirm_password">Confirm New Password</Label>
                <Input
                  id="confirm_password"
                  type="password"
                  value={passwordData.confirm_password}
                  onChange={(e) => setPasswordData({ ...passwordData, confirm_password: e.target.value })}
                  required
                />
              </div>

              <Button type="submit" disabled={isPasswordLoading}>
                {isPasswordLoading ? 'Changing...' : 'Change Password'}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Account Information</CardTitle>
          <CardDescription>
            Your account details
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-sm font-medium">Role:</span>
              <span className="text-sm text-gray-600">{formatRole(currentUser?.role)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm font-medium">Department:</span>
              <span className="text-sm text-gray-600">{departmentLabel}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm font-medium">Account Created:</span>
              <span className="text-sm text-gray-600">
                {currentUser?.created_at ? new Date(currentUser.created_at).toLocaleDateString() : 'N/A'}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default Settings;
