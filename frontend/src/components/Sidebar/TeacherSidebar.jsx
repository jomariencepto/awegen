import React, { useEffect, useState } from 'react';
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import LogoutConfirmDialog from '../LogoutConfirmDialog';
import { cn } from '../../utils';
import {
  Bell,
  ChevronLeft,
  ChevronRight,
  LogOut,
  Menu,
  X,
} from 'lucide-react';

const teacherNavigation = [
  { name: 'Dashboard', href: '/teacher/dashboard' },
  { name: 'Upload Module', href: '/teacher/upload-module' },
  { name: 'Module Images', href: '/teacher/module-images' },
  { name: 'Create Exam', href: '/teacher/create-exam' },
  { name: 'Manage Exams', href: '/teacher/manage-exams' },
  { name: 'Notifications', href: '/teacher/notifications' },
];

const TeacherSidebar = () => {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [teacherInfo, setTeacherInfo] = useState({
    name: 'Teacher',
    email: '',
    initials: 'T',
  });

  const handleLogout = () => setShowLogoutConfirm(true);

  const handleProfileClick = () => {
    navigate('/teacher/settings');
    setMobileMenuOpen(false);
  };

  const confirmLogout = async () => {
    if (isLoggingOut) return;
    setIsLoggingOut(true);
    try {
      await logout();
      navigate('/auth/login');
    } finally {
      setIsLoggingOut(false);
      setShowLogoutConfirm(false);
    }
  };

  useEffect(() => {
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    const first = user.first_name || '';
    const last = user.last_name || '';
    const name = user.name || `${first} ${last}`.trim() || 'Teacher';
    const initials =
      first && last
        ? (first[0] + last[0]).toUpperCase()
        : name[0]?.toUpperCase() || 'T';

    setTeacherInfo({
      name,
      email: user.email || '',
      initials,
    });
  }, []);

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    document.body.style.overflow = mobileMenuOpen ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [mobileMenuOpen]);

  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth >= 768) {
        setMobileMenuOpen(false);
      }
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const getPageTitle = () => {
    if (location.pathname === '/teacher/settings') return 'Profile Settings';
    const currentPath = teacherNavigation.find(
      (item) => item.href === location.pathname
    );
    return currentPath ? currentPath.name : 'Teacher';
  };

  const renderNavItems = (isCollapsed = false, isMobile = false) =>
    teacherNavigation.map((item) => {
      const active = location.pathname === item.href;
      return (
        <Link
          key={item.name}
          to={item.href}
          className={cn(
            'flex items-center rounded-xl text-sm font-medium transition-all relative',
            isMobile ? 'px-4 py-3' : 'px-3 py-3',
            active
              ? 'bg-amber-200 text-amber-900 border border-amber-300'
              : 'text-amber-800 hover:bg-amber-100 border border-transparent',
            isCollapsed ? 'justify-center' : 'gap-3'
          )}
          title={isCollapsed ? item.name : undefined}
        >
          {active && (
            <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-amber-500 rounded-r-full" />
          )}
          <span className="truncate">
            {isCollapsed ? item.name.charAt(0) : item.name}
          </span>
          {!isCollapsed && active && (
            <div className="ml-auto w-1.5 h-1.5 bg-amber-500 rounded-full" />
          )}
        </Link>
      );
    });

  return (
    <>
      <div className="flex h-screen w-full bg-gray-50 overflow-hidden">
        <aside
          className={cn(
            'hidden md:flex bg-amber-50 border-r border-amber-200 flex-col transition-all duration-300 flex-shrink-0 shadow-sm',
            collapsed ? 'w-20' : 'w-64'
          )}
        >
          <div className="flex items-center justify-between px-4 py-4 border-b border-amber-200 h-16">
            {!collapsed && (
              <Link
                to="/teacher/dashboard"
                className="flex items-center gap-3 hover:opacity-80 transition-opacity"
              >
                <img
                  src="/pdm.png"
                  alt="PDM Logo"
                  className="h-14 w-14 object-contain"
                />
                <span className="font-bold text-lg text-gray-900">AWEgen</span>
              </Link>
            )}
            {collapsed && (
              <Link
                to="/teacher/dashboard"
                className="flex items-center justify-center hover:opacity-80 transition-opacity"
              >
                <img
                  src="/pdm.png"
                  alt="PDM Logo"
                  className="h-12 w-12 object-contain"
                />
              </Link>
            )}
            <button
              onClick={() => setCollapsed((prev) => !prev)}
              className="p-2 rounded-lg hover:bg-amber-100 text-amber-800 transition-colors"
              type="button"
              aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {collapsed ? (
                <ChevronRight className="h-5 w-5" />
              ) : (
                <ChevronLeft className="h-5 w-5" />
              )}
            </button>
          </div>

          <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
            {renderNavItems(collapsed, false)}
          </nav>

          <div className="p-4 border-t border-amber-200 bg-amber-50/60">
            {collapsed ? (
              <div className="space-y-2">
                <button
                  onClick={handleProfileClick}
                  type="button"
                  className="flex w-full items-center justify-center p-2 rounded-lg hover:bg-amber-100 transition-all"
                  title="Profile settings"
                  aria-label="Profile settings"
                >
                  <span className="w-9 h-9 bg-gradient-to-br from-amber-100 to-amber-200 rounded-full flex items-center justify-center font-semibold text-amber-800 text-xs border-2 border-amber-300">
                    {teacherInfo.initials}
                  </span>
                </button>
                <button
                  onClick={handleLogout}
                  type="button"
                  className="flex w-full items-center justify-center p-2.5 text-amber-700 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all"
                  title="Logout"
                  aria-label="Logout"
                >
                  <LogOut className="h-5 w-5" />
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                <button
                  type="button"
                  onClick={handleProfileClick}
                  className="flex w-full items-center gap-3 px-2 py-2 rounded-lg hover:bg-amber-100 transition-colors text-left"
                  title="Profile settings"
                >
                  <div className="w-10 h-10 bg-gradient-to-br from-amber-100 to-amber-200 rounded-full flex items-center justify-center font-semibold text-amber-800 text-sm border-2 border-amber-300">
                    {teacherInfo.initials}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-900 truncate">
                      {teacherInfo.name}
                    </p>
                    <p className="text-xs text-gray-500 truncate">
                      {teacherInfo.email}
                    </p>
                  </div>
                </button>
                <Button
                  onClick={handleLogout}
                  variant="outline"
                  size="sm"
                  className="w-full border-amber-300 text-amber-800 hover:bg-amber-100 hover:border-amber-400 gap-2"
                >
                  <LogOut className="h-4 w-4" />
                  Logout
                </Button>
              </div>
            )}
          </div>
        </aside>

        {mobileMenuOpen && (
          <div className="md:hidden">
            <div
              className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40"
              onClick={() => setMobileMenuOpen(false)}
              aria-hidden="true"
            />
            <aside className="fixed left-0 top-0 bottom-0 w-72 max-w-[85vw] bg-white shadow-2xl z-50 flex flex-col">
              <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 h-16">
                <Link
                  to="/teacher/dashboard"
                  className="flex items-center gap-3 hover:opacity-80 transition-opacity"
                >
                  <img
                    src="/pdm.png"
                    alt="PDM Logo"
                    className="h-12 w-12 object-contain"
                  />
                  <span className="font-bold text-lg text-gray-900">AWEgen</span>
                </Link>
                <button
                  onClick={() => setMobileMenuOpen(false)}
                  type="button"
                  className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                  aria-label="Close menu"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
                {renderNavItems(false, true)}
              </nav>

              <div className="p-4 border-t border-gray-100 bg-gray-50">
                <button
                  type="button"
                  onClick={handleProfileClick}
                  className="flex w-full items-center gap-3 px-2 py-2 mb-3 rounded-lg hover:bg-white transition-colors text-left"
                  title="Profile settings"
                >
                  <div className="w-10 h-10 bg-gradient-to-br from-yellow-100 to-yellow-200 rounded-full flex items-center justify-center font-semibold text-yellow-700 text-sm border-2 border-yellow-300">
                    {teacherInfo.initials}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-900 truncate">
                      {teacherInfo.name}
                    </p>
                    <p className="text-xs text-gray-500 truncate">
                      {teacherInfo.email}
                    </p>
                  </div>
                </button>
                <Button
                  onClick={handleLogout}
                  variant="outline"
                  size="sm"
                  className="w-full border-gray-200 text-gray-600 hover:bg-red-50 hover:text-red-600 hover:border-red-300 gap-2"
                >
                  <LogOut className="h-4 w-4" />
                  Logout
                </Button>
              </div>
            </aside>
          </div>
        )}

        <div className="flex-1 flex flex-col min-w-0 bg-gray-50/50">
          <header className="bg-white border-b border-gray-200 h-16 flex items-center px-4 sm:px-6 flex-shrink-0 shadow-sm">
            <button
              onClick={() => setMobileMenuOpen(true)}
              type="button"
              className="md:hidden p-2 mr-3 hover:bg-gray-100 rounded-lg transition-colors"
              aria-label="Open menu"
            >
              <Menu className="h-6 w-6" />
            </button>

            <div className="flex-1 min-w-0">
              <h1 className="text-lg sm:text-xl font-bold text-gray-900 truncate">
                {getPageTitle()}
              </h1>
            </div>

            <div className="flex items-center gap-2 sm:gap-3">
              <Link to="/teacher/notifications">
                <Button
                  variant="ghost"
                  size="icon"
                  className="relative hover:bg-amber-100 transition-colors text-amber-800"
                >
                  <Bell className="h-5 w-5" />
                  <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border-2 border-white" />
                </Button>
              </Link>
            </div>
          </header>

          <main className="flex-1 p-4 sm:p-6 overflow-y-auto">
            <div className="max-w-[1400px] mx-auto">
              <Outlet />
            </div>
          </main>

          <footer className="bg-white border-t border-gray-200 text-center py-3 text-xs text-gray-500 flex-shrink-0 px-2">
            (c) {new Date().getFullYear()} AWEgen - Pambayang Dalubhasaan ng Marilao
          </footer>
        </div>
      </div>

      <LogoutConfirmDialog
        open={showLogoutConfirm}
        onCancel={() => setShowLogoutConfirm(false)}
        onConfirm={confirmLogout}
        title="Are you sure to log out?"
        message="You will need to sign in again to continue."
        confirmLabel={isLoggingOut ? 'Logging out...' : 'Confirm'}
        cancelLabel="Cancel"
        isProcessing={isLoggingOut}
      />
    </>
  );
};

export default TeacherSidebar;
