/**
 * An email drawn in a sandboxed frame, as a reader sees it in a mail program.
 *
 * Nothing in the email can run or reach the portal: the frame allows no scripts, no
 * forms, and no same-origin access.  It allows only popups that leave the sandbox, and
 * every link in the email opens in a new tab (a `<base target="_blank">` put at the
 * head of the email), so a reader can follow a newsletter's links without the page
 * they are reading being replaced.
 */
import type { JSX } from 'react';

/** The sandbox: popups only, which may leave it, and nothing else. */
export const EMAIL_FRAME_SANDBOX = 'allow-popups allow-popups-to-escape-sandbox';

/** What is put at the head of every email, so its links open in a new tab. */
const NEW_TAB_BASE = '<base target="_blank" rel="noopener">';

/**
 * `html` with its links set to open in a new tab: the base element goes just inside
 * `<head>` when the email has one, and first otherwise.
 */
export function withNewTabLinks(html: string): string {
  const head = /<head(\s[^>]*)?>/i.exec(html);
  if (head === null) return `${NEW_TAB_BASE}${html}`;
  const at = head.index + head[0].length;
  return `${html.slice(0, at)}${NEW_TAB_BASE}${html.slice(at)}`;
}

export interface EmailFrameProps {
  /** The frame's accessible name, such as "The email as Ann Able received it". */
  title: string;
  /** The whole HTML email. */
  html: string;
}

/** The email `html` in a sandboxed frame whose links open in a new tab. */
export function EmailFrame({ title, html }: EmailFrameProps): JSX.Element {
  return (
    <iframe
      className="email-frame"
      title={title}
      sandbox={EMAIL_FRAME_SANDBOX}
      srcDoc={withNewTabLinks(html)}
    />
  );
}
