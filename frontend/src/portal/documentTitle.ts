/**
 * The browser tab's title for each portal screen: the screen's own title, then the
 * organization's name ("Member check · CalDART"), so tabs, history, and a screen
 * reader can tell the screens apart.
 */
import { useEffect } from 'react';

/** The organization's name, which Django stamps on `<html>` as `data-org-name`. */
export const ORG_NAME: string = document.documentElement.dataset.orgName ?? 'CalDART';

/** The document title for a screen titled `title`: `Member check · CalDART`. */
export function documentTitle(title: string): string {
  return `${title} · ${ORG_NAME}`;
}

/** Set the document title to `title` followed by the organization's name while mounted. */
export function useDocumentTitle(title: string): void {
  useEffect(() => {
    document.title = documentTitle(title);
  }, [title]);
}
