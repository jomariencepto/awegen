import React, { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '../../components/ui/card';
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from '../../components/ui/select';
import { Alert, AlertDescription } from '../../components/ui/alert';
import api from '../../utils/api';
import { toast } from 'react-hot-toast';
import TermsCheckbox from '../../components/TermsAndConditions';
import { Eye, EyeOff } from 'lucide-react';
import useAuthPageScroll from '../../hooks/useAuthPageScroll';

function SignupDepartment() {
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

  // Locked school selection
  const DEFAULT_SCHOOL_ID = 1;
  const DEFAULT_SCHOOL_NAME = 'Pambayang Dalubhasaan ng Marilao';

  const { register, handleSubmit, setValue, watch, formState: { errors } } = useForm();
  useAuthPageScroll();
  const passwordValue = watch('password');
  const sanitizeName = (value) => value.replace(/[^A-Za-z\s'-]/g, '');
  const handleNameInput = (field) => (event) => {
    const cleaned = sanitizeName(event.target.value);
    setValue(field, cleaned, { shouldValidate: true, shouldDirty: true });
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [deptRes] = await Promise.all([
          api.get('/users/departments')
        ]);

        setDepartments(deptRes.data.departments || []);

        // Pre-fill locked school value
        setValue('school_id_number', DEFAULT_SCHOOL_ID, { shouldValidate: true });
      } catch (error) {
        console.error('Error fetching data:', error);
        toast.error('Failed to load departments');
        setError('Failed to load required data. Please refresh the page.');
      }
    };
    fetchData();
  }, []);

  const onRegisterSubmit = async (data) => {
    setIsLoading(true);
    setError('');
    
    try {
      // Convert IDs to proper types
      const { confirm_password, ...rest } = data;

      const registrationData = {
        ...rest,
        role_id: 3, // Department Head role (role_id 3 = department)
        school_id_number: DEFAULT_SCHOOL_ID,
        department_id: parseInt(data.department_id, 10)
        // NO subject_id - not in your database
      };
      
      const result = await registerUser(registrationData);
      
      if (result.success) {
        setEmailForOTP(data.email);
        setShowOTP(true);
      } else {
        setError(result.message || 'Registration failed');
      }
    } catch (error) {
      console.error('Registration submission error:', error);
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
      console.error('OTP submission error:', error);
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
        <CardHeader className="text-center">
          <CardTitle className="text-2xl font-bold">
            <button
              type="button"
              className="inline text-current"
              onClick={() => navigate('/auth/signup-admin')}
              aria-label="Hidden shortcut to Admin signup"
              style={{ cursor: 'pointer' }}
            >
              D
            </button>
            epartment Head Registration
          </CardTitle>
          <CardDescription>
            {showOTP ? 'Enter the OTP sent to your email' : 'Create a new department head account'}
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
                  <Label htmlFor="first_name">First Name *</Label>
                  <Input 
                    id="first_name"
                    className={errors.first_name ? 'border-red-500 focus:ring-red-500 focus:border-red-500' : ''}
                    onChange={handleNameInput('first_name')}
                    onInput={handleNameInput('first_name')}
                    {...register('first_name', { required: 'First name is required', pattern: { value: /^[A-Za-z\s'-]+$/, message: 'Letters only' } })} 
                    placeholder="John"
                  />
                  {errors.first_name && (
                    <span className="text-red-500 text-sm">{errors.first_name.message}</span>
                  )}
                </div>
                <div>
                  <Label htmlFor="last_name">Last Name *</Label>
                  <Input 
                    id="last_name"
                    className={errors.last_name ? 'border-red-500 focus:ring-red-500 focus:border-red-500' : ''}
                    onChange={handleNameInput('last_name')}
                    onInput={handleNameInput('last_name')}
                    {...register('last_name', { required: 'Last name is required', pattern: { value: /^[A-Za-z\s'-]+$/, message: 'Letters only' } })} 
                    placeholder="Doe"
                  />
                  {errors.last_name && (
                    <span className="text-red-500 text-sm">{errors.last_name.message}</span>
                  )}
                </div>
              </div>

              <div>
                <Label htmlFor="email">Email *</Label>
                <Input 
                  id="email"
                  type="email" 
                  {...register('email', { 
                    required: 'Email is required',
                    pattern: {
                      value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                      message: 'Invalid email address'
                    }
                  })} 
                  placeholder="dept.head@example.com"
                />
                {errors.email && (
                  <span className="text-red-500 text-sm">{errors.email.message}</span>
                )}
              </div>

              
<div>
  <Label htmlFor="password">Password *</Label>
  <div className="relative">
    <Input 
      id="password"
      type={showPassword ? 'text' : 'password'} 
      className="pr-10"
      {...register('password', { 
        required: 'Password is required',
        minLength: {
          value: 8,
          message: 'Password must be at least 8 characters'
        },
        pattern: {
          value: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*(),.?":{}|<>]).{8,}$/,
          message: 'Use upper, lower, number, and special character'
        }
      })} 
      placeholder="********"
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
    <span className="text-red-500 text-sm">{errors.password.message}</span>
  )}
</div>

<div>
  <Label htmlFor="confirm_password">Confirm Password *</Label>
  <div className="relative">
    <Input 
      id="confirm_password"
      type={showConfirmPassword ? 'text' : 'password'} 
      className="pr-10"
      {...register('confirm_password', { 
        required: 'Please confirm your password',
        validate: (value) => value === passwordValue || 'Passwords do not match'
      })} 
      placeholder="********"
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
    <span className="text-red-500 text-sm">{errors.confirm_password.message}</span>
  )}
</div>

              <div>
    <Label htmlFor="school">School *</Label>
                <Input
                  id="school"
                  value={DEFAULT_SCHOOL_NAME}
                  readOnly
                  className="bg-gray-100"
                />
                <input
                  type="hidden"
                  value={DEFAULT_SCHOOL_ID}
                  {...register('school_id_number', { required: 'School is required' })}
                />
              </div>

              <div>
                <Label htmlFor="department">Department *</Label>
                <Select 
                  onValueChange={(val) => { 
                    setValue('department_id', val, { shouldValidate: true }); 
                  }}
                >
                  <SelectTrigger id="department">
                    <SelectValue placeholder="Select department" />
                  </SelectTrigger>
                  <SelectContent>
                    {departments.length === 0 ? (
                      <SelectItem value="no-departments" disabled>No departments available</SelectItem>
                    ) : (
                      departments.map((d) => (
                        <SelectItem 
                          key={d.department_id} 
                          value={d.department_id.toString()}
                        >
                          {d.department_name}
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
                <input 
                  type="hidden" 
                  {...register('department_id', { required: 'Department is required' })} 
                />
                {errors.department_id && (
                  <span className="text-red-500 text-sm">{errors.department_id.message}</span>
                )}
              </div>
              <TermsCheckbox
                checked={agreedToTerms}
                onCheckedChange={setAgreedToTerms}
              />
            </CardContent>

            <CardFooter className="flex flex-col space-y-2">
              <Button type="submit" className="w-full" disabled={isLoading || !agreedToTerms}>
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
              <div>
                <Label htmlFor="otp_code">Enter 6-digit OTP *</Label>
                <Input 
                  id="otp_code"
                  {...register('otp_code', { 
                    required: 'OTP is required',
                    pattern: {
                      value: /^[0-9]{6}$/,
                      message: 'OTP must be exactly 6 digits'
                    }
                  })} 
                  placeholder="123456"
                  maxLength={6}
                />
                {errors.otp_code && (
                  <span className="text-red-500 text-sm">{errors.otp_code.message}</span>
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

export default SignupDepartment;

