import type { JSX, ReactNode } from 'react';

import { Card } from '@/portal/components/Card';
import { useDocumentTitle } from '@/portal/documentTitle';

import './auth.css';

export interface AuthShellProps {
  /** The screen's only `h1`. */
  title: string;
  /** One sentence under the title. */
  lede?: string;
  /** The card's content: the form, or what the screen says once it is done. */
  children: ReactNode;
  /** A line below the card, such as the link to join. */
  footer?: ReactNode;
}

/**
 * The one frame for the screens a person meets on the way in (sign in, forgot and
 * reset password, verify email): a centered panel no wider than 26rem holding a
 * centered title, an optional lede, the card, and an optional footer line below it.
 * Inside the card, an `.auth__actions` block stacks a full-width submit button above
 * a centered secondary link.  The title also names the browser tab.  Changing a
 * password or an email address while signed in is a portal page (`Page`) instead.
 */
export function AuthShell({ title, lede, children, footer }: AuthShellProps): JSX.Element {
  useDocumentTitle(title);
  return (
    <div className="auth">
      <div className="auth__panel">
        <h1 className="auth__title">{title}</h1>
        {lede ? <p className="muted auth__lede">{lede}</p> : null}
        <Card className="auth-card">{children}</Card>
        {footer ? <p className="muted auth__footer">{footer}</p> : null}
      </div>
    </div>
  );
}
