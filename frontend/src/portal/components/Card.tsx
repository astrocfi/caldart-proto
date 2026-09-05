import type { ReactNode } from 'react';

export interface CardProps {
  title?: ReactNode;
  eyebrow?: string;
  footer?: ReactNode;
  className?: string;
  children?: ReactNode;
}

/** A flat panel with a hairline border — no shadow, near-square corners. */
export function Card({ title, eyebrow, footer, className, children }: CardProps) {
  return (
    <section className={className ? `card ${className}` : 'card'}>
      {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
      {title ? <h2 className="card__title">{title}</h2> : null}
      {children}
      {footer ? <div className="card__footer cluster">{footer}</div> : null}
    </section>
  );
}
