import React, { createContext, useContext, useEffect, useState } from 'react';
import { toast } from 'react-hot-toast';
import api from '../utils/api';
import { getUserRole } from '../utils/api';

const AuthContext = createContext();

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // On mount, try to fetch current user via cookie-based session.
    // Also support legacy localStorage token during migration.
    const token = localStorage.getItem('token');
    if (token) {
      api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    }

    const hasJwtCookie =
      typeof document !== 'undefined' &&
      document.cookie.includes('access_token_cookie=');

    const onPublicAuthRoute =
      typeof window !== 'undefined' &&
      window.location.pathname.startsWith('/auth/');

    // Avoid a noisy 401 on public auth pages when no token/cookie is present.
    if (!token && !hasJwtCookie && onPublicAuthRoute) {
      setLoading(false);
      return;
    }

    fetchCurrentUser();
  }, []);

  const fetchCurrentUser = async () => {
    try {
      const response = await api.get('/auth/me', { skipAuthRefresh: true });

      const formattedUser = {
        ...response.data.user,
        role: getUserRole(response.data.user)
      };

      setCurrentUser(formattedUser);
      setIsAuthenticated(true);

      // If we still have a legacy token, clean it up — cookies are handling auth now
      if (localStorage.getItem('token')) {
        localStorage.removeItem('token');
        delete api.defaults.headers.common['Authorization'];
      }
    } catch {
      // Not authenticated — clear any stale data
      localStorage.removeItem('token');
      delete api.defaults.headers.common['Authorization'];
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    try {
      const response = await api.post('/auth/login', { email, password });

      const { user } = response.data;

      if (!user) {
        throw new Error('Invalid response from server');
      }

      // Backward compat: if backend still returns access_token in body,
      // store it so the request interceptor can attach it as Bearer header
      // until cookies are fully established.
      if (response.data.access_token) {
        localStorage.setItem('token', response.data.access_token);
        api.defaults.headers.common['Authorization'] = `Bearer ${response.data.access_token}`;
      }

      const formattedUser = {
        ...user,
        role: getUserRole(user)
      };

      setCurrentUser(formattedUser);
      setIsAuthenticated(true);

      toast.success('Login successful!');

      return { success: true, user: formattedUser };
    } catch (error) {
      const message = error.response?.data?.message || 'Login failed';
      toast.error(message);
      return { success: false, message };
    }
  };

  const register = async (userData) => {
    try {
      const roleId = parseInt(userData.role_id);

      // Admin (role_id = 1) needs school but NOT department
      if (roleId === 1) {
        if (!userData.school_id_number) {
          toast.error('School selection is required for Admin');
          return { success: false, message: 'School is required' };
        }
        const { department_id, ...adminData } = userData;
        const response = await api.post('/auth/register', adminData);
        toast.success('Registration successful! Check your email for OTP.');
        return { success: true, data: response.data };
      }

      // Teacher (role_id = 2) and Department Head (role_id = 3) need both
      if (roleId === 2) {
        if (!userData.school_id_number) {
          toast.error('School selection is required');
          return { success: false, message: 'School is required' };
        }
        if (!userData.department_id) {
          toast.error('Department selection is required');
          return { success: false, message: 'Department is required' };
        }
        const response = await api.post('/auth/register', userData);
        toast.success('Registration successful! Check your email for OTP.');
        return { success: true, data: response.data };
      }
      if (roleId === 3) {
        if (!userData.school_id_number) {
          toast.error('School selection is required');
          return { success: false, message: 'School is required' };
        }
        if (!userData.department_id) {
          toast.error('Department selection is required');
          return { success: false, message: 'Department is required' };
        }
        const response = await api.post('/auth/register', userData);
        toast.success('Registration successful! Check your email for OTP.');
        return { success: true, data: response.data };
      }

      toast.error('Invalid role selected');
      return { success: false, message: 'Invalid role' };

    } catch (error) {
      const message = error.response?.data?.message || 'Registration failed';
      toast.error(message);
      return { success: false, message };
    }
  };

  const verifyOTP = async (email, otp_code, purpose = 'registration') => {
    try {
      const response = await api.post('/auth/verify-otp', { email, otp_code, purpose });
      toast.success('OTP verified successfully!');
      return { success: true, data: response.data };
    } catch (error) {
      const message = error.response?.data?.message || 'OTP verification failed';
      toast.error(message);
      return { success: false, message };
    }
  };

  const requestOTP = async (email, purpose = 'registration') => {
    try {
      await api.post('/auth/request-otp', { email, purpose });
      toast.success('A new OTP was sent to your email');
      return { success: true };
    } catch (error) {
      const message = error.response?.data?.message || 'Failed to send OTP';
      toast.error(message);
      return { success: false, message };
    }
  };

  const requestPasswordReset = async (email) => {
    try {
      await api.post('/auth/request-otp', { email, purpose: 'password_reset' });
      toast.success('Reset code sent to your email!');
      return { success: true };
    } catch (error) {
      const message = error.response?.data?.message || 'Failed to send reset code';
      toast.error(message);
      return { success: false, message };
    }
  };

  const verifyPasswordReset = async (email, otp_code, new_password) => {
    try {
      await api.post('/auth/reset-password', { email, otp_code, new_password });
      toast.success('Password reset successfully!');
      return { success: true };
    } catch (error) {
      const message = error.response?.data?.message || 'Password reset failed';
      toast.error(message);
      return { success: false, message };
    }
  };

  const logout = async () => {
    try {
      await api.post('/auth/logout');
    } catch {
      // Logout endpoint might fail if already expired — continue cleanup
    }
    localStorage.removeItem('token');
    delete api.defaults.headers.common['Authorization'];
    setCurrentUser(null);
    setIsAuthenticated(false);
    toast.success('Logged out successfully');
  };

  const value = {
    currentUser,
    isAuthenticated,
    loading,
    login,
    register,
    verifyOTP,
    requestOTP,
    requestPasswordReset,
    verifyPasswordReset,
    logout,
  };

  return (
    <AuthContext.Provider value={value}>
      {!loading && children}
    </AuthContext.Provider>
  );
}
