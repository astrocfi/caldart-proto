import type { ButtonHTMLAttributes, JSX, ReactNode } from 'react';
import { Link } from 'react-router-dom';

export type ButtonVariant = 'primary' | 'secondary' | 'quiet' | 'danger';

const VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary: '',
  secondary: 'button--secondary',
  quiet: 'button--quiet',
  danger: 'button--danger',
};

function classNames(variant: ButtonVariant, small: boolean, extra?: string): string {
  return ['button', VARIANT_CLASS[variant], small ? 'button--small' : '', extra ?? '']
    .filter(Boolean)
    .join(' ');
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  small?: boolean;
  children: ReactNode;
}

/** A styled `<button>` in the design system's primary, secondary, quiet, or danger variant. */
export function Button({
  variant = 'primary',
  small = false,
  className,
  type = 'button',
  children,
  ...rest
}: ButtonProps): JSX.Element {
  return (
    <button type={type} className={classNames(variant, small, className)} {...rest}>
      {children}
    </button>
  );
}

export interface ButtonLinkProps {
  to: string;
  variant?: ButtonVariant;
  small?: boolean;
  className?: string;
  children: ReactNode;
}

/** A router link that looks like a button. */
export function ButtonLink({
  to,
  variant = 'primary',
  small = false,
  className,
  children,
}: ButtonLinkProps): JSX.Element {
  return (
    <Link to={to} className={classNames(variant, small, className)}>
      {children}
    </Link>
  );
}
