import type { ReactNode } from 'react';

export interface PageProps {
  title: string;
  /** Small-caps label above the title. */
  eyebrow?: string;
  /** One-sentence description under the title. */
  lede?: string;
  /** Buttons or links aligned with the title. */
  actions?: ReactNode;
  children?: ReactNode;
}

/** The standard portal page frame: header rule, title block, then content. */
export function Page({ title, eyebrow, lede, actions, children }: PageProps) {
  return (
    <article className="page">
      <header className="page__header">
        <div>
          {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
          <h1 className="page__title">{title}</h1>
          {lede ? <p className="lede page__lede">{lede}</p> : null}
        </div>
        {actions ? <div className="cluster page__actions">{actions}</div> : null}
      </header>
      <div className="page__body stack-loose">{children}</div>
    </article>
  );
}
