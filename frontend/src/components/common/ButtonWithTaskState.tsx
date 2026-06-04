import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const variantClass: Record<ButtonVariant, string> = {
  primary: "primary-button",
  secondary: "secondary-button",
  ghost: "ghost-button",
  danger: "danger-button"
};

export interface ButtonWithTaskStateProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "type"> {
  children: ReactNode;
  isRunning?: boolean;
  runningLabel?: ReactNode;
  taskKind?: string;
  type?: "button" | "submit" | "reset";
  variant?: ButtonVariant;
}

export function ButtonWithTaskState({
  children,
  className,
  disabled,
  isRunning = false,
  onClick,
  runningLabel,
  taskKind,
  type = "button",
  variant = "secondary",
  ...rest
}: ButtonWithTaskStateProps) {
  const classes = [variantClass[variant], className].filter(Boolean).join(" ");

  return (
    <button
      {...rest}
      aria-busy={isRunning || undefined}
      className={classes}
      data-task-kind={taskKind}
      disabled={disabled || isRunning}
      onClick={onClick}
      type={type}
    >
      {isRunning ? runningLabel || children : children}
    </button>
  );
}
