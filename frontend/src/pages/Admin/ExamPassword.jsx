import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Eye, EyeOff, Loader2, Save, ShieldAlert, ShieldCheck } from 'lucide-react';
import api from '../../utils/api';

function ExamPassword() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [status, setStatus] = useState({
    is_configured: false,
    masked_password: '',
    min_password_length: 4,
  });
  const [form, setForm] = useState({
    password: '',
    confirm_password: '',
  });
  const [message, setMessage] = useState({ type: '', text: '' });

  const loadSettings = async () => {
    setLoading(true);
    try {
      const response = await api.get('/admin/exam-password');
      const settings = response.data?.settings || {};
      setStatus({
        is_configured: Boolean(settings.is_configured),
        masked_password: settings.masked_password || '',
        min_password_length: Number(settings.min_password_length) || 4,
      });
    } catch (error) {
      setMessage({
        type: 'error',
        text: error.response?.data?.message || 'Failed to load exam password settings.',
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSettings();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage({ type: '', text: '' });

    const password = form.password.trim();
    const confirmPassword = form.confirm_password.trim();
    const minLength = status.min_password_length || 4;

    if (!password) {
      setMessage({ type: 'error', text: 'Password is required.' });
      return;
    }
    if (password.length < minLength) {
      setMessage({ type: 'error', text: `Password must be at least ${minLength} characters.` });
      return;
    }
    if (password !== confirmPassword) {
      setMessage({ type: 'error', text: 'Passwords do not match.' });
      return;
    }

    setSaving(true);
    try {
      const response = await api.put('/admin/exam-password', { password });
      setMessage({
        type: 'success',
        text: response.data?.message || 'Exam password updated successfully.',
      });
      setForm({ password: '', confirm_password: '' });
      setShowPassword(false);
      setShowConfirmPassword(false);
      await loadSettings();
    } catch (error) {
      setMessage({
        type: 'error',
        text: error.response?.data?.message || 'Failed to update exam password.',
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Exam Password</h1>
        <p className="text-muted-foreground">
          Change the password used when exporting protected exam PDF and DOCX files.
        </p>
      </div>

      {message.text && (
        <div
          className={`p-4 rounded-md flex items-center ${
            message.type === 'success'
              ? 'bg-green-50 text-green-800 border border-green-200'
              : 'bg-red-50 text-red-800 border border-red-200'
          }`}
        >
          {message.type === 'success' ? (
            <ShieldCheck className="h-5 w-5 mr-2" />
          ) : (
            <ShieldAlert className="h-5 w-5 mr-2" />
          )}
          <span className="text-sm font-medium">{message.text}</span>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Current Status</CardTitle>
          <CardDescription>
            This password is used to protect downloaded exam PDF and DOCX files.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p>
            <span className="font-medium">Configured:</span>{' '}
            {loading ? 'Loading...' : status.is_configured ? 'Yes' : 'No'}
          </p>
          {status.is_configured && (
            <p>
              <span className="font-medium">Current (masked):</span> {status.masked_password}
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Update Password</CardTitle>
          <CardDescription>
            Enter a new password and confirm it. You can show or hide password text.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="exam_password">New Exam Password</Label>
              <div className="relative">
                <Input
                  id="exam_password"
                  type={showPassword ? 'text' : 'password'}
                  value={form.password}
                  onChange={(e) => setForm((prev) => ({ ...prev, password: e.target.value }))}
                  placeholder="Enter new exam password"
                  minLength={status.min_password_length || 4}
                  autoComplete="new-password"
                  className="pr-12"
                  required
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute right-1 top-1 h-8 w-8"
                  onClick={() => setShowPassword((prev) => !prev)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="exam_password_confirm">Confirm Password</Label>
              <div className="relative">
                <Input
                  id="exam_password_confirm"
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={form.confirm_password}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, confirm_password: e.target.value }))
                  }
                  placeholder="Confirm new exam password"
                  minLength={status.min_password_length || 4}
                  autoComplete="new-password"
                  className="pr-12"
                  required
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute right-1 top-1 h-8 w-8"
                  onClick={() => setShowConfirmPassword((prev) => !prev)}
                  aria-label={showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}
                >
                  {showConfirmPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Minimum length: {status.min_password_length || 4} characters.
              </p>
            </div>

            <div className="pt-2 flex justify-end">
              <Button type="submit" disabled={saving || loading} className="min-w-[150px]">
                {saving ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Save className="mr-2 h-4 w-4" />
                    Save Password
                  </>
                )}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

export default ExamPassword;
