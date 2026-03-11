import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '../../components/ui/card';
import { Alert, AlertDescription } from '../../components/ui/alert';
import { Eye, EyeOff } from 'lucide-react';
import { toast } from 'react-hot-toast';
import TermsCheckbox from '../../components/TermsAndConditions';
import useAuthPageScroll from '../../hooks/useAuthPageScroll';

function SignupAdmin() {
  const { register: registerUser, verifyOTP, requestOTP } = useAuth();
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);
  const [showOTP, setShowOTP] = useState(false);
  const [emailForOTP, setEmailForOTP] = useState('');
  const [error, setError] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [agreedToTerms, setAgreedToTerms] = useState(false);
  const [isResendingOTP, setIsResendingOTP] = useState(false);

  const DEFAULT_SCHOOL_ID = 1;
  const DEFAULT_SCHOOL_NAME = 'Pambayang Dalubhasaan ng Marilao';
  const ADMIN_ROLE_ID = 1;
  const ADMIN_TYPE_LABEL = 'School Admin';
  const ADMIN_LEVEL = 'school';
  
  const { register, handleSubmit, setValue, watch, formState: { errors } } = useForm();
  useAuthPageScroll();
  const password = watch('password');
  const sanitizeName = (value) => value.replace(/[^A-Za-z\s'-]/g, '');
  const handleNameInput = (field) => (event) => {
    const cleaned = sanitizeName(event.target.value);
    setValue(field, cleaned, { shouldValidate: true, shouldDirty: true });
  };

  // Keep form values in sync with fixed admin role/level
  useEffect(() => {
    setValue('admin_type', 'admin', { shouldValidate: true });
    setValue('admin_level', ADMIN_LEVEL, { shouldValidate: true });
    setValue('school_id_number', DEFAULT_SCHOOL_ID, { shouldValidate: true });
  }, [setValue]);

  // Strong password validation
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

  const onRegisterSubmit = async (data) => {
    setIsLoading(true);
    setError('');
    
    try {
      const { confirm_password, ...rest } = data;
      
      const registrationData = {
        ...rest,
        role_id: ADMIN_ROLE_ID,
        admin_level: ADMIN_LEVEL,
        admin_type: 'admin',
        school_id_number: DEFAULT_SCHOOL_ID,
      };

      const result = await registerUser(registrationData);
      
      if (result.success) {
        setEmailForOTP(data.email);
        setShowOTP(true);
        toast.success('OTP sent to your email');
      } else {
        setError(result.message || 'Registration failed');
      }
    } catch (error) {
      console.error('Registration error:', error);
      setError('An unexpected error occurred. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const onOTPSubmit = async (data) => {
    setIsLoading(true);
    setError('');
    
    try {
      const result = await verifyOTP(emailForOTP, data.otp_code, 'registration');
      
      if (result.success) {
        toast.success('Account verified! You can now login.');
        setTimeout(() => navigate('/auth/login'), 1500);
      } else {
        setError(result.message || 'OTP verification failed');
      }
    } catch (error) {
      console.error('OTP verification error:', error);
      setError('An unexpected error occurred. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendOTP = async () => {
    if (!emailForOTP) return;
    setIsResendingOTP(true);
    try {
      await requestOTP(emailForOTP, 'registration');
    } finally {
      setIsResendingOTP(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 px-4 py-4 sm:py-8">
      <div className="mx-auto flex w-full max-w-md items-start justify-center sm:min-h-[calc(100vh-4rem)] sm:items-center">
      <Card className="w-full">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold text-center">
            Admin Registration
          </CardTitle>
          <CardDescription className="text-center">
            {showOTP ? 'Enter the OTP sent to your email' : 'Create a new administrator account'}
          </CardDescription>
        </CardHeader>
        
        {error && (
          <div className="px-6 pb-4">
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          </div>
        )}
        
        {!showOTP ? (
          <form onSubmit={handleSubmit(onRegisterSubmit)}>
            <CardContent className="space-y-4">
              {/* Admin Type (locked, hidden toggle via level control) */}
              <div className="space-y-2">
                <Label htmlFor="admin_type">Admin Type *</Label>
                <Input
                  id="admin_type_display"
                  value={ADMIN_TYPE_LABEL}
                  readOnly
                  className="bg-gray-100"
                />
                <input 
                  type="hidden" 
                  {...register('admin_type', { required: 'Admin type is required' })} 
                />
              </div>

              {/* Name Fields */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="first_name">First Name *</Label>
                  <Input
                    id="first_name"
                    placeholder="John"
                    className={errors.first_name ? 'border-red-500 focus:ring-red-500 focus:border-red-500' : ''}
                    onChange={handleNameInput('first_name')}
                    onInput={handleNameInput('first_name')}
                    {...register('first_name', {
                      required: 'First name is required',
                      pattern: { value: /^[A-Za-z\s'-]+$/, message: 'Letters only' },
                    })}
                  />
                  {errors.first_name && (
                    <p className="text-sm text-red-500">{errors.first_name.message}</p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="last_name">Last Name *</Label>
                  <Input
                    id="last_name"
                    placeholder="Doe"
                    className={errors.last_name ? 'border-red-500 focus:ring-red-500 focus:border-red-500' : ''}
                    onChange={handleNameInput('last_name')}
                    onInput={handleNameInput('last_name')}
                    {...register('last_name', {
                      required: 'Last name is required',
                      pattern: { value: /^[A-Za-z\s'-]+$/, message: 'Letters only' },
                    })}
                  />
                  {errors.last_name && (
                    <p className="text-sm text-red-500">{errors.last_name.message}</p>
                  )}
                </div>
              </div>
              
              {/* Email */}
              <div className="space-y-2">
                <Label htmlFor="email">Email *</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="admin@example.com"
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
              
              {/* Password */}
              <div className="space-y-2">
                <Label htmlFor="password">Password *</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    className="pr-10"
                    {...register('password', {
                      required: 'Password is required',
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
                {errors.password && (
                  <p className="text-sm text-red-500">{errors.password.message}</p>
                )}
                <p className="text-xs text-gray-500">
                  Must contain: 8+ characters, uppercase, lowercase, number, special character
                </p>
              </div>
              
              {/* Confirm Password */}
              <div className="space-y-2">
                <Label htmlFor="confirm_password">Confirm Password *</Label>
                <div className="relative">
                  <Input
                    id="confirm_password"
                    type={showConfirmPassword ? "text" : "password"}
                    placeholder="••••••••"
                    className="pr-10"
                    {...register('confirm_password', {
                      required: 'Please confirm your password',
                      validate: (value) => 
                        value === password || 
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
              
              <div className="space-y-2">
                <Label htmlFor="school_id_number">School *</Label>
                <Input
                  id="school_id_number_display"
                  value={DEFAULT_SCHOOL_NAME}
                  readOnly
                  className="bg-gray-100"
                />
                <input
                  type="hidden"
                  value={DEFAULT_SCHOOL_ID}
                  {...register('school_id_number', { required: 'School is required for Admin' })}
                />
              </div>
              
              {/* Admin Level (locked display) */}
              <div className="space-y-1">
                <Label htmlFor="admin_level">Admin Level *</Label>
                <Input
                  id="admin_level_display"
                  value={ADMIN_TYPE_LABEL}
                  readOnly
                  className="bg-gray-100"
                />
                <input 
                  type="hidden" 
                  {...register('admin_level', { required: 'Admin level is required' })} 
                />
                {errors.admin_level && (
                  <p className="text-sm text-red-500">{errors.admin_level.message}</p>
                )}
              </div>
              
              {/* Employee ID */}
              <div className="space-y-2">
                <Label htmlFor="employee_id">Employee ID *</Label>
                <Input
                  id="employee_id"
                  placeholder="ADM-001"
                  {...register('employee_id', {
                    required: 'Employee ID is required',
                    pattern: {
                      value: /^[A-Za-z0-9-]+$/,
                      message: 'Use letters, numbers, and hyphen only',
                    },
                  })}
                />
                {errors.employee_id && (
                  <p className="text-sm text-red-500">{errors.employee_id.message}</p>
                )}
              </div>
              <TermsCheckbox
                checked={agreedToTerms}
                onCheckedChange={setAgreedToTerms}
              />
            </CardContent>

            <CardFooter className="flex flex-col space-y-2">
              <Button
                type="submit"
                className="w-full"
                disabled={isLoading || !agreedToTerms}
              >
                {isLoading ? 'Registering...' : 'Register'}
              </Button>
              <p className="text-sm text-center text-gray-600">
                Already have an account?{' '}
                <Link to="/auth/login" className="text-blue-600 hover:underline">
                  Login here
                </Link>
              </p>
            </CardFooter>
          </form>
        ) : (
          <form onSubmit={handleSubmit(onOTPSubmit)}>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="otp_code">Enter 6-digit OTP *</Label>
                <Input
                  id="otp_code"
                  placeholder="123456"
                  maxLength={6}
                  {...register('otp_code', {
                    required: 'OTP is required',
                    pattern: {
                      value: /^[0-9]{6}$/,
                      message: 'OTP must be 6 digits',
                    },
                  })}
                />
                {errors.otp_code && (
                  <p className="text-sm text-red-500">{errors.otp_code.message}</p>
                )}
              </div>
              <p className="text-sm text-gray-600">
                OTP sent to: <strong>{emailForOTP}</strong>
              </p>
            </CardContent>
            <CardFooter className="flex flex-col space-y-2">
              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? 'Verifying...' : 'Verify OTP'}
              </Button>
              <Button
                type="button"
                variant="outline"
                className="w-full"
                onClick={handleResendOTP}
                disabled={isResendingOTP || isLoading}
              >
                {isResendingOTP ? 'Sending OTP...' : 'Resend OTP'}
              </Button>
              <Button 
                type="button" 
                variant="outline" 
                className="w-full"
                onClick={() => {
                  setShowOTP(false);
                  setError('');
                }}
              >
                Back to Registration
              </Button>
            </CardFooter>
          </form>
        )}
      </Card>
      </div>
    </div>
  );
}

export default SignupAdmin;
