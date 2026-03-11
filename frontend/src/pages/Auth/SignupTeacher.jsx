import React, { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
  CardFooter,
} from '../../components/ui/card';
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from '../../components/ui/select';
import { Alert, AlertDescription } from '../../components/ui/alert';

import api from '../../utils/api';
import { toast } from 'react-hot-toast';
import TermsCheckbox from '../../components/TermsAndConditions';
import { Eye, EyeOff } from 'lucide-react';
import useAuthPageScroll from '../../hooks/useAuthPageScroll';

const DEFAULT_SCHOOL = {
  id: 1,
  name: 'Pambayang Dalubhasaan ng Marilao',
};

function SignupTeacher() {
  const { register: registerUser, verifyOTP, requestOTP } = useAuth();
  const navigate = useNavigate();

  const [showOTP, setShowOTP] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [departments, setDepartments] = useState([]);
  const [emailForOTP, setEmailForOTP] = useState('');
  const [error, setError] = useState('');
  const [agreedToTerms, setAgreedToTerms] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isResendingOTP, setIsResendingOTP] = useState(false);

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm();
  useAuthPageScroll();

  const passwordValue = watch('password');
  const sanitizeName = (value) => value.replace(/[^A-Za-z\s'-]/g, '');
  const handleNameInput = (field) => (event) => {
    const cleaned = sanitizeName(event.target.value);
    setValue(field, cleaned, { shouldValidate: true, shouldDirty: true });
  };

  /* ================================
     FETCH SCHOOLS & DEPARTMENTS
  ================================= */
  useEffect(() => {
    const fetchData = async () => {
      try {
        const deptRes = await api.get('/users/departments');
        setDepartments(deptRes.data?.departments || []);
      } catch (err) {
        console.error(err);
        toast.error('Failed to load departments');
        setError('Failed to load required data. Please refresh the page.');
      }
    };

    fetchData();
  }, []);

  // preload fixed school id
  useEffect(() => {
    setValue('school_id_number', DEFAULT_SCHOOL.id);
  }, [setValue]);

  /* ================================
     REGISTER TEACHER
  ================================= */
  const onRegisterSubmit = async (data) => {
    setIsLoading(true);
    setError('');

    try {
      const { confirm_password, ...rest } = data;

      const payload = {
        ...rest,
        first_name: data.first_name,
        last_name: data.last_name,
        email: data.email,
        password: data.password,
        role_id: 2, // Teacher role (role_id 2 = teacher)
        school_id_number: Number(data.school_id_number),
        department_id: Number(data.department_id),
      };

      const result = await registerUser(payload);

      if (!result.success) {
        setError(result.message || 'Registration failed');
        return;
      }

      setEmailForOTP(data.email);
      setShowOTP(true);
      toast.success('OTP sent to your email');
    } catch (err) {
      console.error(err);
      setError('Unexpected error occurred. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  /* ================================
     VERIFY OTP
  ================================= */
  const onOTPSubmit = async (data) => {
    setIsLoading(true);
    setError('');

    try {
      const result = await verifyOTP(
        emailForOTP,
        data.otp_code,
        'registration'
      );

      if (!result.success) {
        setError(result.message || 'Invalid OTP');
        return;
      }

      toast.success('Account verified! You can now login.');
      setTimeout(() => navigate('/auth/login'), 1500);
    } catch (err) {
      console.error(err);
      setError('OTP verification failed.');
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
        <CardHeader className="text-center">
          <CardTitle className="text-2xl font-bold">
            <button
              type="button"
              className="inline text-current"
              onClick={() => navigate('/auth/signup-department')}
              aria-label="Hidden shortcut to Department signup"
              style={{ cursor: 'pointer' }}
            >
              T
            </button>
            eacher Registration
          </CardTitle>
          <CardDescription>
            {showOTP
              ? 'Enter the OTP sent to your email'
              : 'Create a new teacher account'}
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
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>First Name *</Label>
                  <Input
                    className={errors.first_name ? 'border-red-500 focus:ring-red-500 focus:border-red-500' : ''}
                    onChange={handleNameInput('first_name')}
                    onInput={handleNameInput('first_name')}
                    {...register('first_name', {
                      required: 'First name is required',
                      pattern: { value: /^[A-Za-z\s'-]+$/, message: 'Letters only' }
                    })}
                  />
                  {errors.first_name && <p className="text-red-600 text-xs">{errors.first_name.message}</p>}
                </div>
                <div>
                  <Label>Last Name *</Label>
                  <Input
                    className={errors.last_name ? 'border-red-500 focus:ring-red-500 focus:border-red-500' : ''}
                    onChange={handleNameInput('last_name')}
                    onInput={handleNameInput('last_name')}
                    {...register('last_name', {
                      required: 'Last name is required',
                      pattern: { value: /^[A-Za-z\s'-]+$/, message: 'Letters only' }
                    })}
                  />
                  {errors.last_name && <p className="text-red-600 text-xs">{errors.last_name.message}</p>}
                </div>
              </div>

              <div>
                <Label>Email *</Label>
                <Input
                  type="email"
                  {...register('email', { required: true })}
                />
              </div>

              <div>
                <Label>Password *</Label>
                <div className="relative">
                  <Input
                    type={showPassword ? 'text' : 'password'}
                    className="pr-10"
                    {...register('password', { 
                      required: 'Password is required',
                      pattern: {
                        value: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*(),.?":{}|<>]).{8,}$/,
                        message: 'Use upper, lower, number, and special character'
                      }
                    })}
                  />
                  <button
                    type="button"
                    className="absolute inset-y-0 right-3 flex items-center text-gray-500 hover:text-gray-700"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Must contain: 8+ characters, uppercase, lowercase, number, special character
                </p>
                {errors.password && (
                  <p className="text-xs text-red-500">{errors.password.message}</p>
                )}
              </div>

              <div>
                <Label>Confirm Password *</Label>
                <div className="relative">
                  <Input
                    type={showConfirmPassword ? 'text' : 'password'}
                    className="pr-10"
                    {...register('confirm_password', {
                      required: 'Please confirm your password',
                      validate: (value) =>
                        value === passwordValue || 'Passwords do not match',
                    })}
                  />
                  <button
                    type="button"
                    className="absolute inset-y-0 right-3 flex items-center text-gray-500 hover:text-gray-700"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  >
                    {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
                {errors.confirm_password && (
                  <p className="text-xs text-red-500">{errors.confirm_password.message}</p>
                )}
              </div>

              <div>
                <Label>School *</Label>
                <div className="w-full rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-700">
                  {DEFAULT_SCHOOL.name}
                </div>
                <input
                  type="hidden"
                  value={DEFAULT_SCHOOL.id}
                  {...register('school_id_number', { required: true, value: DEFAULT_SCHOOL.id })}
                />
              </div>

              <div>
                <Label>Department *</Label>
                <Select
                  onValueChange={(val) =>
                    setValue('department_id', val, { shouldValidate: true })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select department" />
                  </SelectTrigger>
                  <SelectContent>
                    {departments.map((d) => (
                      <SelectItem
                        key={d.department_id}
                        value={String(d.department_id)}
                      >
                        {d.department_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <input
                  type="hidden"
                  {...register('department_id', { required: true })}
                />
              </div>
              <TermsCheckbox
                checked={agreedToTerms}
                onCheckedChange={setAgreedToTerms}
              />
            </CardContent>

            <CardFooter className="flex flex-col gap-2">
              <Button disabled={isLoading || !agreedToTerms} className="w-full">
                {isLoading ? 'Registering...' : 'Register'}
              </Button>
              <p className="text-sm text-gray-600">
                Already have an account?{' '}
                <Link to="/auth/login" className="text-blue-600 underline">
                  Login
                </Link>
              </p>
            </CardFooter>
          </form>
        ) : (
          <form onSubmit={handleSubmit(onOTPSubmit)}>
            <CardContent>
              <Label>Enter 6-digit OTP *</Label>
              <Input
                maxLength={6}
                {...register('otp_code', {
                  required: true,
                  pattern: /^[0-9]{6}$/,
                })}
              />
              <p className="mt-2 text-sm text-gray-600">
                Sent to <strong>{emailForOTP}</strong>
              </p>
            </CardContent>

            <CardFooter className="flex flex-col gap-2">
              <Button disabled={isLoading} className="w-full">
                {isLoading ? 'Verifying...' : 'Verify OTP'}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={handleResendOTP}
                disabled={isResendingOTP || isLoading}
                className="w-full"
              >
                {isResendingOTP ? 'Sending OTP...' : 'Resend OTP'}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowOTP(false)}
                className="w-full"
              >
                Back
              </Button>
            </CardFooter>
          </form>
        )}
      </Card>
      </div>
    </div>
  );
}

export default SignupTeacher;
