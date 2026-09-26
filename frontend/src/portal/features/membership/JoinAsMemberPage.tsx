/**
 * `/membership/join` — a friend of CalDART pays dues and becomes a member.
 *
 * The page is the join checkout and nothing else: paying for a plan is what makes a
 * friend a member, the moment the payment succeeds.  Leaving the page changes nothing.
 */
import { useQueryClient } from '@tanstack/react-query';
import type { JSX } from 'react';
import { useNavigate } from 'react-router-dom';

import { Page } from '@/portal/components/Page';
import { useToast } from '@/portal/components/Toast';
import { Checkout } from '@/portal/features/checkout';
import { refreshAfterPayment } from '@/portal/features/join/refresh';

/** What the member reads once the payment has gone through. */
export const JOINED_TOAST = 'Thank you — you are a member of CalDART.';

/** Renders the join checkout for a signed-in friend, and goes home once they have paid. */
export function JoinAsMemberPage(): JSX.Element {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();

  function handleSuccess() {
    refreshAfterPayment(queryClient);
    toast.show(JOINED_TOAST, 'success');
    void navigate('/');
  }

  return (
    <Page
      title="Become a member"
      eyebrow="Membership"
      lede="Choose a plan and pay your dues: you are a member of CalDART as soon as the payment goes through. Nothing changes if you leave this page."
    >
      <Checkout mode="join" onSuccess={handleSuccess} />
    </Page>
  );
}
