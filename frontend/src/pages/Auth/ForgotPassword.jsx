import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '../../components/ui/card';
import { Eye, EyeOff } from 'lucide-react';

function ForgotPassword() {
  const { requestPasswordReset, verifyPasswordReset } = useAuth();
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);
  const [showOTP, setShowOTP] = useState(false);
  const [email, setEmail] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  
  const {
    handleSubmit,
    register,
    reset,
    watch,
    formState: { errors },
  } = useForm();

  const newPassword = watch('new_password');

  // Strong password validation function
  const validateStrongPassword = (value) => {
    if (value.length < 8) {
      return 'Password must be at least 8 characters';
    }
    if (!/[A-Z]/.test(value)) {
      return 'Password must contain at least one uppercase letter';
    }
    if (!/[a-z]/.test(value)) {
      return 'Password must contain at least one lowercase letter';
    }
    if (!/[0-9]/.test(value)) {
      return 'Password must contain at least one number';
    }
    if (!/[!@#$%^&*(),.?":{}|<>]/.test(value)) {
      return 'Password must contain at least one special character (!@#$%^&*(),.?":{}|<>)';
    }
    return true;
  };

  const onRequestSubmit = async (data) => {
    setIsLoading(true);
    try {
      const result = await requestPasswordReset(data.email);
      if (result.success) {
        setEmail(data.email);
        setShowOTP(true);
        reset({
          otp_code: '',
          new_password: '',
          confirm_password: '',
        });
      }
    } catch (error) {
      console.error('Error requesting password reset:', error);
    }
    setIsLoading(false);
  };

  const onResetSubmit = async (data) => {
    setIsLoading(true);
    try {
      const result = await verifyPasswordReset(email, data.otp_code, data.new_password);
      if (result.success) {
        navigate('/auth/login');
      }
    } catch (error) {
      console.error('Error resetting password:', error);
    }
    setIsLoading(false);
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold text-center">
            Reset Password
          </CardTitle>
          <CardDescription className="text-center">
            {!showOTP 
              ? "Enter your email to receive a password reset code"
              : "Enter the code and your new password"
            }
          </CardDescription>
        </CardHeader>
        
        {!showOTP ? (
          <form onSubmit={handleSubmit(onRequestSubmit)}>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email *</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="name@example.com"
                  autoComplete="email"
                  {...register('email', {
                    required: 'Email is required',
                    pattern: {
                      value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                      message: 'Invalid email address',
                    },
                  })}
                />
                {errors.email && (
                  <p className="text-sm text-red-500">{errors.email.message}</p>
                )}
              </div>
            </CardContent>
            <CardFooter>
              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? 'Sending...' : 'Send Reset Code'}
              </Button>
            </CardFooter>
          </form>
        ) : (
          <form onSubmit={handleSubmit(onResetSubmit)}>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="otp_code">Reset Code *</Label>
                <Input
                  id="otp_code"
                  type="text"
                  placeholder="123456"
                  maxLength={6}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  autoCapitalize="off"
                  autoCorrect="off"
                  spellCheck={false}
                  {...register('otp_code', {
                    required: 'Reset code is required',
                    pattern: {
                      value: /^[0-9]{6}$/,
                      message: 'Code must be 6 digits',
                    },
                  })}
                />
                {errors.otp_code && (
                  <p className="text-sm text-red-500">{errors.otp_code.message}</p>
                )}
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="new_password">New Password *</Label>
                <div className="relative">
                  <Input
                    id="new_password"
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    className="pr-10"
                    autoComplete="new-password"
                    {...register('new_password', {
                      required: 'New password is required',
                      validate: validateStrongPassword,
                    })}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
                  >
                    {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                  </button>
                </div>
                {errors.new_password && (
                  <p className="text-sm text-red-500">{errors.new_password.message}</p>
                )}
                <p className="text-xs text-gray-500">
                  Must contain: 8+ characters, uppercase, lowercase, number, special character
                </p>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="confirm_password">Confirm Password *</Label>
                <div className="relative">
                  <Input
                    id="confirm_password"
                    type={showConfirmPassword ? "text" : "password"}
                    placeholder="••••••••"
                    className="pr-10"
                    autoComplete="new-password"
                    {...register('confirm_password', {
                      required: 'Please confirm your password',
                      validate: (value) => 
                        value === newPassword || 
                        'Passwords do not match',
                    })}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
                  >
                    {showConfirmPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                  </button>
                </div>
                {errors.confirm_password && (
                  <p className="text-sm text-red-500">{errors.confirm_password.message}</p>
                )}
              </div>
            </CardContent>
            <CardFooter>
              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? 'Resetting...' : 'Reset Password'}
              </Button>
            </CardFooter>
          </form>
        )}
        
        <CardFooter className="flex justify-center">
          <div className="text-center text-sm">
            Remembered your password?{' '}
            <Link to="/auth/login" className="text-blue-600 hover:underline">
              Login
            </Link>
          </div>
        </CardFooter>
      </Card>
    </div>
  );
}

export default ForgotPassword;
