import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '../../components/ui/card';

function AdminManagedSignupNotice({ accountLabel = 'teacher or department-head' }) {
  return (
    <div className="min-h-screen bg-gray-100 px-4 py-8">
      <div className="mx-auto flex w-full max-w-xl items-center justify-center">
        <Card className="w-full">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-bold text-gray-900">
              Account Creation Is Managed by Admin
            </CardTitle>
            <CardDescription>
              Public self-signup for {accountLabel} accounts is no longer available.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-gray-700">
            <p>
              Please contact your school administrator so they can create your account from the
              admin panel.
            </p>
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-left">
              <p className="font-medium text-amber-900">Admin path</p>
              <p className="mt-1 text-amber-800">
                <span className="font-semibold">Admin</span> &gt; <span className="font-semibold">Users</span> &gt; <span className="font-semibold">Create Account</span>
              </p>
            </div>
            <p>If you already have an account, you can go back to login.</p>
          </CardContent>
          <CardFooter className="flex flex-col gap-2 sm:flex-row">
            <Button asChild className="w-full">
              <Link to="/auth/login">Back to Login</Link>
            </Button>
            <Button asChild variant="outline" className="w-full">
              <Link to="/auth/forgot-password">Forgot Password</Link>
            </Button>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}

export default AdminManagedSignupNotice;
