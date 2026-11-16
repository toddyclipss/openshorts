import React, { Component } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Unhandled UI error caught by ErrorBoundary:', error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-paper flex flex-col items-center justify-center p-6 text-center">
          <div className="max-w-md w-full bg-paper2 border border-rule rounded-card p-6 shadow-card space-y-4">
            <div className="w-12 h-12 rounded-full bg-red-500/10 text-red-500 flex items-center justify-center mx-auto">
              <AlertCircle size={24} />
            </div>
            <h2 className="font-display lowercase text-xl text-ink">Something went wrong</h2>
            <p className="text-sm text-muted">
              {this.state.error?.message || 'A frontend error occurred while rendering the page.'}
            </p>
            <div className="pt-2">
              <button
                onClick={this.handleReload}
                className="btn-primary w-full flex items-center justify-center gap-2 py-2"
              >
                <RefreshCw size={16} />
                Reload Page
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
