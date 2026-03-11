import React, { useEffect, useState } from 'react';
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import LogoutConfirmDialog from '../LogoutConfirmDialog';
import { cn } from '../../utils';
import { ChevronLeft, ChevronRight, LogOut, Menu, X } from 'lucide-react';

const adminNavigation = [
  { name: 'Dashboard', href: '/admin/dashboard' },
  { name: 'Users', href: '/admin/users' },
  { name: 'Departments & Subjects', href: '/admin/departments-subjects' },
  { name: 'System Reports', href: '/admin/system-reports' },
  { name: 'Exam Password', href: '/admin/exam-password' },
];

const AdminSidebar = () => {
  const { currentUser, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [adminInfo, setAdminInfo] = useState({
    name: 'Administrator',
    email: '',
    initials: 'AD',
  });

  const handleLogout = () => setShowLogoutConfirm(true);

  const handleProfileClick = () => {
    navigate('/admin/settings');
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
    const name = user.name || `${first} ${last}`.trim() || 'Administrator';
    const initials =
      first && last
        ? (first[0] + last[0]).toUpperCase()
        : name[0]?.toUpperCase() || 'AD';

    setAdminInfo({
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
    if (location.pathname === '/admin/settings') return 'Profile Settings';
    const currentPath = adminNavigation.find(
      (item) => item.href === location.pathname
    );
    return currentPath ? currentPath.name : 'Admin';
  };

  const renderNavItems = (isCollapsed = false, isMobile = false) =>
    adminNavigation.map((item) => {
      const active = location.pathname === item.href;
      return (
        <Link
          key={item.name}
          to={item.href}
          className={cn(
            'flex items-center text-sm font-medium transition-colors rounded-xl relative',
            isMobile ? 'px-4 py-3' : 'px-3 py-2.5',
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
    <div className="flex h-screen w-full overflow-hidden bg-gray-50">
      <aside
        className={cn(
          'hidden md:flex bg-amber-50 border-r border-amber-200 shadow-sm flex-col flex-shrink-0 transition-all duration-300',
          collapsed ? 'w-16' : 'w-64'
        )}
      >
        <div className="flex items-center justify-between p-3 border-b border-amber-200 h-16">
          {!collapsed && (
            <Link
              to="/admin/dashboard"
              className="flex items-center gap-2 hover:opacity-80 transition-opacity"
            >
              <img src="/pdm.png" alt="PDM Logo" className="h-10 w-10 object-contain" />
              <span className="text-xl font-bold">AWEgen</span>
            </Link>
          )}
          {collapsed && (
            <Link
              to="/admin/dashboard"
              className="flex items-center justify-center hover:opacity-80 transition-opacity"
            >
              <img src="/pdm.png" alt="PDM Logo" className="h-10 w-10 object-contain" />
            </Link>
          )}
          <button
            onClick={() => setCollapsed((prev) => !prev)}
            className="p-1 rounded hover:bg-amber-100 text-amber-800"
            type="button"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <ChevronRight /> : <ChevronLeft />}
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-1">
          {renderNavItems(collapsed, false)}
        </nav>

        <div className="p-3 border-t border-amber-200 bg-amber-50/60">
          {collapsed ? (
            <div className="space-y-2">
              <button
                type="button"
                onClick={handleProfileClick}
                className="flex w-full items-center justify-center p-2 rounded-lg hover:bg-amber-100 transition-colors"
                title="Profile settings"
                aria-label="Profile settings"
              >
                <span className="w-9 h-9 bg-amber-100 rounded-full flex items-center justify-center font-semibold text-amber-800 border-2 border-amber-300 text-xs">
                  {adminInfo.initials}
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
                <div className="w-10 h-10 bg-amber-100 rounded-full flex items-center justify-center font-semibold text-amber-800 border-2 border-amber-300">
                  {adminInfo.initials}
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{adminInfo.name}</p>
                  <p className="truncate text-xs text-gray-500">{adminInfo.email}</p>
                </div>
              </button>
              <Button
                onClick={handleLogout}
                size="sm"
                variant="outline"
                className="w-full border-amber-300 text-amber-800 hover:bg-amber-100 hover:border-amber-400"
              >
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
                to="/admin/dashboard"
                className="flex items-center gap-2 hover:opacity-80 transition-opacity"
              >
                <img src="/pdm.png" alt="PDM Logo" className="h-10 w-10 object-contain" />
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

            <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
              {renderNavItems(false, true)}
            </nav>

            <div className="p-4 border-t border-gray-100 bg-gray-50">
              <button
                type="button"
                onClick={handleProfileClick}
                className="flex w-full items-center gap-3 px-2 py-2 mb-3 rounded-lg hover:bg-white transition-colors text-left"
                title="Profile settings"
              >
                <div className="w-10 h-10 bg-amber-100 rounded-full flex items-center justify-center font-semibold text-amber-800 border-2 border-amber-300">
                  {adminInfo.initials}
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{adminInfo.name}</p>
                  <p className="truncate text-xs text-gray-500">{adminInfo.email}</p>
                </div>
              </button>
              <Button
                onClick={handleLogout}
                size="sm"
                variant="outline"
                className="w-full border-gray-300 text-gray-700 hover:bg-red-50 hover:text-red-600 hover:border-red-300"
              >
                Logout
              </Button>
            </div>
          </aside>
        </div>
      )}

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="h-16 px-4 sm:px-6 flex items-center justify-between border-b bg-white">
          <div className="flex items-center gap-2 min-w-0">
            <button
              onClick={() => setMobileMenuOpen(true)}
              type="button"
              className="md:hidden p-2 rounded-lg hover:bg-gray-100 transition-colors"
              aria-label="Open menu"
            >
              <Menu className="h-6 w-6" />
            </button>
            <h1 className="text-lg sm:text-xl font-semibold truncate">{getPageTitle()}</h1>
          </div>
          <span className="hidden sm:inline text-sm text-gray-600 truncate max-w-[220px]">
            {currentUser?.first_name} {currentUser?.last_name}
          </span>
        </header>

        <main className="flex-1 overflow-y-auto p-4 sm:p-6 w-full">
          <Outlet />
        </main>

        <footer className="border-t py-3 text-center text-xs text-gray-500 bg-white px-2">
          (c) {new Date().getFullYear()} AWEgen
        </footer>
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
    </div>
  );
};

export default AdminSidebar;
