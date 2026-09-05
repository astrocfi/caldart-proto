import type { ReactNode } from 'react';

export interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
}

/** Shown instead of an empty table or list. */
export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <p className="empty-state__title">{title}</p>
      {description ? <p className="empty-state__body muted">{description}</p> : null}
      {action ? <div className="cluster empty-state__action">{action}</div> : null}
    </div>
  );
}
