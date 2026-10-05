import { useEffect, useRef } from 'react';
import type { JSX, ReactNode } from 'react';
import { useLocation } from 'react-router-dom';

import { useDocumentTitle } from '@/portal/documentTitle';
import { navEyebrow } from '@/portal/nav';

/**
 * The navigation state that asks the page arrived at to take the focus to its title, for
 * an action whose button the move takes away, such as **Add member** opening the record it
 * made: `navigate(path, { state: FOCUS_TITLE })`.
 */
export const FOCUS_TITLE = { focusTitle: true } as const;

/** True when `state`, a location's navigation state, is `FOCUS_TITLE`'s. */
function asksForTitleFocus(state: unknown): boolean {
  return typeof state === 'object' && state !== null && 'focusTitle' in state;
}

export interface PageProps {
  title: string;
  /**
   * The browser tab's name, when the heading is not the screen's name: the
   * dashboard's greeting, say.  The title otherwise.
   */
  tabTitle?: string;
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
 * (or `tabTitle`) also names the browser tab, followed by the organization's name.  A
 * page reached with `FOCUS_TITLE` as its navigation state moves the focus to its title.
 */
export function Page({
  title,
  tabTitle,
  noEyebrow = false,
  lede,
  actions,
  children,
}: PageProps): JSX.Element {
  const { pathname, state, key } = useLocation();
  const eyebrow = noEyebrow ? null : navEyebrow(pathname);
  useDocumentTitle(tabTitle ?? title);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const shouldFocusTitle = asksForTitleFocus(state);
  useEffect(() => {
    const heading = titleRef.current;
    if (!shouldFocusTitle || heading === null) return;
    heading.tabIndex = -1;
    heading.focus();
  }, [shouldFocusTitle, key]);
  return (
    <article className="page">
      <header className="page__header">
        {eyebrow !== null ? <p className="eyebrow">{eyebrow}</p> : null}
        <div className="page__heading">
          <h1 ref={titleRef} className="page__title">
            {title}
          </h1>
          {actions ? <div className="cluster page__actions">{actions}</div> : null}
        </div>
        {lede ? <p className="lede page__lede">{lede}</p> : null}
      </header>
      <div className="page__body stack-loose">{children}</div>
    </article>
  );
}
