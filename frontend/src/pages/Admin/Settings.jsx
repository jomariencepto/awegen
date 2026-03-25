import React, { useEffect, useState } from 'react';
import { CheckCircle2, Loader2, Lock, Save, Shield, User } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import api from '../../utils/api';

const formatRole = (role) => {
  if (!role) return 'Loading...';
  return String(role)
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

function Settings() {
  const { currentUser, refreshCurrentUser } = useAuth();
  const [profileData, setProfileData] = useState({
    first_name: '',
    last_name: '',
    email: '',
  });
  const [passwordData, setPasswordData] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });
  const [emailChangePassword, setEmailChangePassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  useEffect(() => {
    setProfileData({
      first_name: currentUser?.first_name || '',
      last_name: currentUser?.last_name || '',
      email: currentUser?.email || '',
    });
    setEmailChangePassword('');
  }, [currentUser]);

  const normalizedCurrentEmail = String(currentUser?.email || '').trim().toLowerCase();
  const normalizedFormEmail = String(profileData.email || '').trim().toLowerCase();
  const isEmailChanged = normalizedFormEmail !== normalizedCurrentEmail;

  const handleProfileUpdate = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage({ type: '', text: '' });

    const firstName = profileData.first_name.trim();
    const lastName = profileData.last_name.trim();
    const email = profileData.email.trim();

    if (!firstName || !lastName || !email) {
      setMessage({ type: 'error', text: 'First name, last name, and email are required.' });
      setLoading(false);
      return;
    }

    if (isEmailChanged && !emailChangePassword) {
      setMessage({ type: 'error', text: 'Current password is required to change your email.' });
      setLoading(false);
      return;
    }

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
      setMessage({ type: 'success', text: response.data?.message || 'Profile updated successfully!' });
      setTimeout(() => setMessage({ type: '', text: '' }), 4000);
    } catch (error) {
      setMessage({ type: 'error', text: error.response?.data?.message || 'Failed to update profile.' });
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordChange = async (e) => {
    e.preventDefault();
    setPasswordLoading(true);
    setMessage({ type: '', text: '' });

    if (passwordData.new_password !== passwordData.confirm_password) {
      setMessage({ type: 'error', text: 'New passwords do not match.' });
      setPasswordLoading(false);
      return;
    }

    try {
      await api.put('/users/change-password', {
        current_password: passwordData.current_password,
        new_password: passwordData.new_password,
      });

      setMessage({ type: 'success', text: 'Password changed successfully!' });
      setPasswordData({ current_password: '', new_password: '', confirm_password: '' });
      setTimeout(() => setMessage({ type: '', text: '' }), 3000);
    } catch (error) {
      setMessage({ type: 'error', text: error.response?.data?.message || 'Failed to change password.' });
    } finally {
      setPasswordLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Manage your account settings and preferences.
        </p>
      </div>

      {message.text && (
        <div className={`p-4 rounded-md flex items-center ${
          message.type === 'success'
            ? 'bg-green-50 text-green-800 border border-green-200'
            : 'bg-red-50 text-red-800 border border-red-200'
        }`}>
          {message.type === 'success' ? (
            <CheckCircle2 className="h-5 w-5 mr-2" />
          ) : (
            <Shield className="h-5 w-5 mr-2" />
          )}
          <span className="text-sm font-medium">{message.text}</span>
        </div>
      )}

      <Tabs defaultValue="profile" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="profile">
            <User className="mr-2 h-4 w-4" />
            Profile
          </TabsTrigger>
          <TabsTrigger value="security">
            <Lock className="mr-2 h-4 w-4" />
            Security
          </TabsTrigger>
        </TabsList>

        <TabsContent value="profile">
          <Card>
            <CardHeader>
              <CardTitle>Profile Information</CardTitle>
              <CardDescription>
                Update your account's personal information here.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleProfileUpdate} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="first_name">First Name</Label>
                    <Input
                      id="first_name"
                      value={profileData.first_name}
                      onChange={(e) => setProfileData({ ...profileData, first_name: e.target.value })}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="last_name">Last Name</Label>
                    <Input
                      id="last_name"
                      value={profileData.last_name}
                      onChange={(e) => setProfileData({ ...profileData, last_name: e.target.value })}
                      required
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="email">Email Address</Label>
                  <Input
                    id="email"
                    type="email"
                    value={profileData.email}
                    onChange={(e) => setProfileData({ ...profileData, email: e.target.value })}
                    required
                  />
                  <p className="text-xs text-muted-foreground">
                    If you change your email, enter your current password below and AWEGen will send a confirmation email to the new address.
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

                <div className="space-y-2">
                  <Label htmlFor="role">Role</Label>
                  <Input
                    id="role"
                    value={formatRole(currentUser?.role)}
                    disabled
                    className="bg-gray-50"
                  />
                </div>

                <div className="pt-4 flex justify-end">
                  <Button type="submit" disabled={loading} className="min-w-[120px]">
                    {loading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <Save className="mr-2 h-4 w-4" />
                        Save Changes
                      </>
                    )}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="security">
          <Card>
            <CardHeader>
              <CardTitle>Change Password</CardTitle>
              <CardDescription>
                Ensure your account is using a strong, unique password.
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

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="new_password">New Password</Label>
                    <Input
                      id="new_password"
                      type="password"
                      value={passwordData.new_password}
                      onChange={(e) => setPasswordData({ ...passwordData, new_password: e.target.value })}
                      required
                      minLength={6}
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
                      minLength={6}
                    />
                  </div>
                </div>

                <div className="pt-4 flex justify-end">
                  <Button type="submit" disabled={passwordLoading} className="min-w-[120px]">
                    {passwordLoading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Updating...
                      </>
                    ) : (
                      <>
                        <Lock className="mr-2 h-4 w-4" />
                        Update Password
                      </>
                    )}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default Settings;
