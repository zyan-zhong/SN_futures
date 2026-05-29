import { Component, type ErrorInfo, type ReactNode } from "react";
import { sanitizeRecord } from "../../utils/sanitize";
import { COPY } from "../../utils/copy";

interface ErrorBoundaryProps {
  moduleName?: string;
  onRetry?: () => void;
  onHome?: () => void;
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null, errorInfo: null };

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ error, errorInfo });
  }

  retry = () => {
    this.setState({ error: null, errorInfo: null });
    this.props.onRetry?.();
  };

  render() {
    const { error, errorInfo } = this.state;
    if (!error) return this.props.children;

    const safeDetails = sanitizeRecord({
      module: this.props.moduleName || "终端模块",
      errorType: error.name,
      message: error.message,
      componentStack: errorInfo?.componentStack || ""
    });

    return (
      <div className="state-box error-state error-boundary" role="alert">
        <strong>{COPY.moduleUnavailable}</strong>
        <span>{this.props.moduleName ? `${this.props.moduleName} 暂时无法显示，请刷新或查看日志。` : "该模块暂时无法显示，请刷新或查看日志。"}</span>
        <div className="button-row">
          <button className="ghost-button" type="button" onClick={this.retry}>
            刷新
          </button>
          {this.props.onHome ? (
            <button className="ghost-button" type="button" onClick={this.props.onHome}>
              返回总览
            </button>
          ) : null}
        </div>
        <details className="debug-panel">
          <summary>{COPY.debugTitle}</summary>
          <pre>{JSON.stringify(safeDetails, null, 2)}</pre>
        </details>
      </div>
    );
  }
}

