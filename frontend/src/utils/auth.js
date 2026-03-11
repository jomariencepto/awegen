export const getUserRole = (user) => {
  return user?.role?.role_name || user?.role || user?.role_name || 'unknown';
};

export const getRoleDashboard = (role) => {
  const dashboards = {
    teacher: '/teacher/dashboard',
    department_head: '/department/dashboard',
    admin: '/admin/dashboard',
  };
  
  return dashboards[role] || '/auth/login';
};

export const isAuthorized = (userRole, requiredRole) => {
  return userRole === requiredRole;
};