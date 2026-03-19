"use client";

import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div className="flex flex-col items-center justify-center p-8 text-center">
            <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mb-4">
              <span className="text-2xl">⚠</span>
            </div>
            <p className="font-semibold text-white/60 mb-2">
              Something went wrong
            </p>
            <p className="text-sm text-white/30 mb-4">
              {this.state.error?.message}
            </p>
            <button
              onClick={() => this.setState({ hasError: false })}
              className="px-4 py-2 rounded-xl bg-white/[0.06] border border-white/[0.08] text-sm hover:bg-white/[0.1] transition"
            >
              Try again
            </button>
          </div>
        )
      );
    }

    return this.props.children;
  }
}
