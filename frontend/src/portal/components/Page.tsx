import type { JSX, ReactNode } from 'react';
import { useLocation } from 'react-router-dom';

import { useDocumentTitle } from '@/portal/documentTitle';
import { navEyebrow } from '@/portal/nav';

export interface PageProps {
  title: string;
  /**
   * Leave the eyebrow off: for a page that belongs to no menu group, such as an
   * error page shown at whatever address failed.
   */
  noEyebrow?: boolean;
  /** One-sentence description under the title. */
  lede?: string;
  /** Buttons or links aligned with the title. */
  actions?: ReactNode;
  children?: ReactNode;
}

/**
 * The standard portal page frame: the eyebrow, the title with its actions beside
 * it, an optional lede, a rule, then the content.
 *
 * The eyebrow is always the menu group the page sits under (`navEyebrow`), so it
 * reads the same as the rail; a page outside the rail has none.  The page's title
 * also names the browser tab, followed by the organization's name.
 */
export function Page({
  title,
  noEyebrow = false,
  lede,
  actions,
  children,
}: PageProps): JSX.Element {
  const { pathname } = useLocation();
  const eyebrow = noEyebrow ? null : navEyebrow(pathname);
  useDocumentTitle(title);
  return (
    <article className="page">
      <header className="page__header">
        {eyebrow !== null ? <p className="eyebrow">{eyebrow}</p> : null}
        <div className="page__heading">
          <h1 className="page__title">{title}</h1>
          {actions ? <div className="cluster page__actions">{actions}</div> : null}
        </div>
        {lede ? <p className="lede page__lede">{lede}</p> : null}
      </header>
      <div className="page__body stack-loose">{children}</div>
    </article>
  );
}
