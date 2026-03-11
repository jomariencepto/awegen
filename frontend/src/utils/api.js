import axios from 'axios';

const isDev = import.meta.env.DEV;

/**
 * IMPORTANT FIX:
 * - Never call http://127.0.0.1:5000 from the browser when using ngrok.
 * - Always use a relative baseURL so requests go to the SAME origin:
 *   https://<your-ngrok-domain> /api/...
 *
 * Your Vite proxy must forward /api -> http://127.0.0.1:5000
 * (you already have this in vite.config.js).
 */
const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,   // send httpOnly cookies on every request
  timeout: 1_200_000,      // 20 minutes
});

const getCookieValue = (cookieName) => {
  if (typeof document === 'undefined') return '';
  const cookies = document.cookie ? document.cookie.split('; ') : [];
  for (const cookie of cookies) {
    const [name, ...rest] = cookie.split('=');
    if (name === cookieName) {
      return decodeURIComponent(rest.join('='));
    }
  }
  return '';
};

// ---- Request interceptor ----
api.interceptors.request.use(
  (config) => {
    // Backward compat: if a token is still in localStorage (migration period),
    // attach it as a Bearer header. Once cookies are fully adopted, remove this.
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    // Cookie-based JWT with CSRF protection:
    // Attach X-CSRF-TOKEN from the matching csrf cookie on unsafe methods.
    const method = String(config.method || 'get').toLowerCase();
    const isUnsafeMethod = ['post', 'put', 'patch', 'delete'].includes(method);
    if (isUnsafeMethod) {
      const isRefreshEndpoint = String(config.url || '').includes('/auth/refresh');
      const csrfCookieName = isRefreshEndpoint ? 'csrf_refresh_token' : 'csrf_access_token';
      const csrfToken = getCookieValue(csrfCookieName);
      if (csrfToken) {
        config.headers = config.headers || {};
        if (!config.headers['X-CSRF-TOKEN']) {
          config.headers['X-CSRF-TOKEN'] = csrfToken;
        }
      }
    }

    if (isDev) {
      // Log the effective URL for debugging
      const methodLabel = String(config.method || 'GET').toUpperCase();
      const url = (config.baseURL || '') + (config.url || '');
      console.log('API Request:', methodLabel, url);
    }

    return config;
  },
  (error) => {
    if (isDev) console.error('Request Error:', error);
    return Promise.reject(error);
  }
);

// ---- Response interceptor with silent refresh ----
let isRefreshing = false;
let failedQueue = [];

const processQueue = (error) => {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error);
    else resolve();
  });
  failedQueue = [];
};

api.interceptors.response.use(
  (response) => {
    if (isDev) {
      console.log('API Response:', response.config.url, response.status);
    }
    return response;
  },
  async (error) => {
    const originalRequest = error.config;

    const status = error.response?.status;
    const url = error.config?.url;
    const method = error.config?.method;

    // Suppress noisy 401 logs for unauthenticated /auth/me checks
    const isUnauthedMe = status === 401 && url === '/auth/me';

    if (isDev && !isUnauthedMe) {
      console.error('API Error:', { status, url, method });
    }

    // --- Silent refresh on 401 ---
    const skipRefresh = originalRequest?.skipAuthRefresh;

    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !skipRefresh &&
      !originalRequest.url?.includes('/auth/login') &&
      !originalRequest.url?.includes('/auth/refresh')
    ) {
      if (isRefreshing) {
        // Queue this request until refresh completes
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(() => api(originalRequest));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Refresh cookie-based session
        await api.post('/auth/refresh');

        processQueue(null);
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError);

        // Refresh failed — clear stale data and redirect to login
        localStorage.removeItem('token');
        localStorage.removeItem('user');

        if (!window.location.pathname.includes('/auth/login')) {
          window.location.href = '/auth/login';
        }

        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    // Handle timeout errors
    if (error.code === 'ECONNABORTED' && isDev) {
      console.error('Request timeout');
    }

    // Handle network errors
    if (error.message === 'Network Error' && isDev) {
      console.error('Network error');
    }

    return Promise.reject(error);
  }
);

export default api;

// ---------------- Role mapping helpers ----------------

export const getUserRole = (user) => {
  if (!user) return 'unknown';

  let role = 'unknown';

  if (typeof user.role === 'object' && user.role !== null) {
    role = user.role.role_name || user.role.name || 'unknown';
  } else if (typeof user.role === 'string') {
    role = user.role;
  } else if (user.role_name) {
    role = user.role_name;
  } else if (user.username) {
    role = user.username;
  }

  if (role === 'department') {
    return 'department_head';
  }

  return role;
};

export const getRoleDashboard = (role) => {
  const dashboards = {
    teacher: '/teacher/dashboard',
    department_head: '/department/dashboard',
    admin: '/admin/dashboard',
    super_admin: '/admin/dashboard',
  };

  return dashboards[role] || '/auth/login';
};

export const isAuthorized = (userRole, requiredRole) => {
  if (userRole === 'department' && requiredRole === 'department_head') {
    return true;
  }
  return userRole === requiredRole;
};
