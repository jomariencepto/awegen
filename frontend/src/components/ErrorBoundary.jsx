import React from 'react';

const isDev = import.meta.env.DEV;


class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });

    if (isDev) {
      console.error('ErrorBoundary caught:', error, errorInfo);
    }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (this.state.hasError) {
      // Custom fallback prop takes priority
      if (this.props.fallback) {
        return this.props.fallback;
      }

      const level = this.props.level || 'app';

      return (
        <div className="min-h-[300px] flex items-center justify-center p-8">
          <div className="max-w-md w-full bg-white rounded-xl border border-gray-200 shadow-sm p-8 text-center">
            <div className="text-red-500 text-5xl mb-4">!</div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
              {level === 'app' ? 'Something went wrong' : 'This section encountered an error'}
            </h2>
            <p className="text-gray-600 mb-6">
              {level === 'app'
                ? 'The application ran into an unexpected error. Please refresh the page.'
                : 'An error occurred in this part of the page. You can try again or navigate elsewhere.'}
            </p>

            {isDev && this.state.error && (
              <pre className="text-left text-xs bg-gray-50 border rounded p-3 mb-4 overflow-auto max-h-40 text-red-700">
                {this.state.error.toString()}
                {this.state.errorInfo?.componentStack}
              </pre>
            )}

            <div className="flex gap-3 justify-center">
              <button
                onClick={this.handleReset}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
              >
                Try Again
              </button>
              {level === 'app' && (
                <button
                  onClick={() => window.location.reload()}
                  className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors text-sm font-medium"
                >
                  Reload Page
                </button>
              )}
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
