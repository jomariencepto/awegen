import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  CardFooter
} from '../../components/ui/card';
import { Eye, EyeOff } from 'lucide-react';
import { getUserRole, getRoleDashboard } from "../../utils/api";
import "./css/login.css";

function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");

    try {
      const result = await login(email, password);
      if (result.success && result.user) {
        const roleName = getUserRole(result.user);

        setTimeout(() => {
          const dashboardPath = getRoleDashboard(roleName);
          
          if (dashboardPath !== '/auth/login') {
            navigate(dashboardPath, { replace: true });
          } else {
            setError(`Role not recognized: ${roleName}. Check console for details.`);
            navigate("/", { replace: true });
          }
        }, 100);
      } else {
        setError(result.message || "Login failed. Please check your credentials.");
      }
    } catch (error) {
      console.error("Login error:", error);
      setError("Login failed. Please check your credentials and try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-container">
      <Card className="login-card">
        <CardHeader className="login-header">
          <div className="brand-logo">
            <div className="logo-icon">
              <img src="/pdm.png" alt="AWEGEN Logo" className="logo-image"/>
            </div>
            <CardTitle className="brand-title text-yellow-600">AWEGen</CardTitle>
          </div>
          <CardDescription className="brand-subtitle">
            AI-Assisted Written Exam Generator
          </CardDescription>
        </CardHeader>
        <CardContent className="login-content">
          {error && (
            <div className="error-message bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
              {error}
            </div>
          )}
          
          <form onSubmit={handleSubmit} className="login-form">
            <div className="form-group">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="form-input"
              />
            </div>
            
            <div className="form-group">
              <div className="password-header">
                <Label htmlFor="password">Password</Label>
                <Link
                  to="/auth/forgot-password"
                  className="forgot-password text-yellow-600 hover:text-yellow-700"
                >
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="form-input pr-10"
                  placeholder="Enter your password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
                >
                  {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                </button>
              </div>
            </div>

            <div className="remember-me">
              <input
                id="remember"
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                className="checkbox"
              />
              <Label htmlFor="remember">Remember me</Label>
            </div>
            
            <Button 
              type="submit" 
              className="login-button bg-yellow-500 hover:bg-yellow-600 text-black" 
              disabled={isLoading}
            >
              {isLoading ? "Signing in..." : "Log In"}
            </Button>
          </form>
          
          <div className="register-prompt">
            <span>Don't have an account yet? </span>
            <Link
              to="/auth/signup"
              className="register-link text-yellow-600 hover:text-yellow-700"
            >
              Register
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default Login;