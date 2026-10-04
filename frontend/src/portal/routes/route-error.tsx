import { useEffect } from 'react';
import type { JSX } from 'react';
import { useRouteError } from 'react-router-dom';

import { Button } from '../components/Button';
import { Page } from '../components/Page';

/**
 * The page shown when a screen fails to load or to draw, in place of React
 * Router's developer error.
 *
 * The usual cause is a screen's code that did not arrive (a dropped connection, or
 * a site upgraded while the tab was open), which a reload fixes.  The error itself
 * goes to the browser console for whoever looks after the site.
 */
export function RouteError(): JSX.Element {
  const error = useRouteError();

  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <Page
      title="This page did not load"
      noEyebrow
      lede="Something went wrong while opening it. Reload the page to try again."
    >
      <div role="alert" className="cluster">
        <Button onClick={() => window.location.reload()}>Reload</Button>
      </div>
    </Page>
  );
}
