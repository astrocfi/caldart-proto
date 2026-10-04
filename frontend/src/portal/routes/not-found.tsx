import type { JSX } from 'react';

import { useAuth } from '../auth/useAuth';
import { ButtonLink } from '../components/Button';
import { Page } from '../components/Page';
import { sitePath } from '../urlPrefix';

/**
 * The 404 page for a portal route that does not exist.
 *
 * A signed-in reader is sent to their dashboard; a visitor who is not signed in is
 * sent to the public site's home page instead, since the dashboard would only ask
 * them to sign in.
 */
export function NotFound(): JSX.Element {
  const { isAuthenticated } = useAuth();
  return (
    <Page
      title="Page not found"
      noEyebrow
      lede={
        isAuthenticated
          ? 'That page is not part of the member portal. Check the address, or go to your dashboard.'
          : 'That page is not part of the member portal. Check the address, or go to the CalDART home page.'
      }
    >
      <div className="cluster">
        {isAuthenticated ? (
          <ButtonLink to="/">Go to the dashboard</ButtonLink>
        ) : (
          <a className="button" href={sitePath('/')}>
            Go to the CalDART home page
          </a>
        )}
      </div>
    </Page>
  );
}
