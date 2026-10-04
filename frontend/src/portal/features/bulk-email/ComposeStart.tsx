/**
 * `/bulk-email/compose`: Compose in the menu. It opens the sender's one empty
 * draft, or makes a fresh one, and moves on to that draft's compose screen at
 * `/bulk-email/compose/:id`, so a sender who presses Compose twice is not left
 * with two empty drafts. A DART leader whose profile names no DART is told why
 * there is nobody to send to instead.
 */
import { useCallback, useEffect, useRef } from 'react';
import type { JSX } from 'react';
import { useNavigate } from 'react-router-dom';

import { Button } from '@/portal/components/Button';
import { Loading } from '@/portal/components/Loading';
import { Page } from '@/portal/components/Page';
import { useBulkSender, useOpenDraft } from './api';
import { SenderNotice } from './SenderNotice';

/** Opens a draft and moves on to it; says so plainly if the server will not. */
export function ComposeStart(): JSX.Element {
  const navigate = useNavigate();
  const sender = useBulkSender();
  const open = useOpenDraft();
  const { mutate } = open;
  // Strict mode mounts effects twice in development; one draft is enough.
  const hasOpened = useRef(false);

  const handleOpen = useCallback((): void => {
    mutate(undefined, {
      onSuccess: (draft) => {
        void navigate(`/bulk-email/compose/${draft.id}`, { replace: true });
      },
    });
  }, [mutate, navigate]);

  const canSend = sender.data?.can_send;
  useEffect(() => {
    if (hasOpened.current || canSend !== true) return;
    hasOpened.current = true;
    handleOpen();
  }, [handleOpen, canSend]);

  if (sender.data !== undefined && !sender.data.can_send) {
    return (
      <Page title="Compose">
        <SenderNotice sender={sender.data} />
      </Page>
    );
  }
  if (!open.isError && !sender.isError) return <Loading />;
  return (
    <Page title="Compose">
      <p className="field__error" role="alert">
        A new email could not be started. Check your connection and try again.
      </p>
      <div className="cluster">
        <Button onClick={handleOpen}>Try again</Button>
      </div>
    </Page>
  );
}
