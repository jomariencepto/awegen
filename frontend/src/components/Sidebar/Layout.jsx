import React, { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Menu, LogOut } from 'lucide-react';

function Layout() {
  const { currentUser, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/auth/login');
  };

  const isTeacherRoute = location.pathname.startsWith('/teacher');

  return (
    <div className="min-h-screen flex flex-col bg-gray-50 w-full">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm flex-shrink-0 sticky top-0 z-50">
        <div className="w-full px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            {!isTeacherRoute && (
              <button
                className="md:hidden p-2 hover:bg-gray-100 rounded-lg transition-colors"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                aria-label="Toggle menu"
              >
                <Menu className="h-6 w-6 text-gray-600" />
              </button>
            )}
            <span className="font-bold text-xl text-yellow-600">AWEGen</span>
          </div>

          <div className="flex items-center gap-4">
            <span className="text-sm font-medium text-gray-700 hidden sm:inline">
              {currentUser?.first_name} {currentUser?.last_name}
            </span>
            <span className="text-xs px-2 py-1 bg-yellow-50 text-yellow-700 rounded-full font-medium hidden md:inline">
              Teacher
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={handleLogout}
              className="border-gray-300 text-gray-700 hover:bg-red-50 hover:border-red-300 hover:text-red-600 transition-all"
              aria-label="Logout"
            >
              <LogOut className="h-4 w-4 mr-1" />
              <span className="hidden sm:inline">Logout</span>
            </Button>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 p-4 md:p-6 w-full max-w-[1920px] mx-auto">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 text-center py-3 text-xs text-gray-500 flex-shrink-0 w-full">
        © {new Date().getFullYear()} AWEGen – Pambayang Dalubhasaan ng Marilao
      </footer>
    </div>
  );
}

export default Layout;