/**
 * The public donation page's script: mounts the donation form on `#donate-app`.
 *
 * `templates/cms/donate_page.html` renders the mount with the address the form reads
 * its configuration from and the address a redirected payment comes back to, and
 * holds the editor's thanks text hidden beside it.  The form runs outside the portal,
 * so it gets a query client and a toast queue of its own and no router.  Once a gift
 * has gone through the thanks text is shown.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { ToastProvider } from '@/portal/components/Toast';
import { DonationForm } from '@/donate/DonationForm';
import '@/portal/portal.css';

/** Show the page's own thanks text, which the template renders hidden. */
function handleGiven(): void {
  const thanks = document.querySelector<HTMLElement>('[data-donate-thanks]');
  if (thanks) thanks.hidden = false;
}

const container = document.getElementById('donate-app');
if (container) {
  const configUrl = container.dataset.configUrl ?? '/api/v1/donations/config';
  const returnUrl = container.dataset.returnUrl ?? window.location.pathname;
  createRoot(container).render(
    <StrictMode>
      <QueryClientProvider client={new QueryClient()}>
        <ToastProvider>
          <DonationForm configUrl={configUrl} returnUrl={returnUrl} onGiven={handleGiven} />
        </ToastProvider>
      </QueryClientProvider>
    </StrictMode>,
  );
}
