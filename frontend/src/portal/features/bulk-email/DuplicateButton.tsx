/**
 * **Duplicate**, on the Sent list and a send's own page: starts a new draft from a
 * bulk email, which stays as it is.
 *
 * The first press asks how: the message alone (its subject, message, and type), or
 * the message and the people, who join the new draft's batch as they are now, so
 * anybody who has since opted out or bounced shows as skipped. The new draft opens on
 * the compose screen.
 */
import type { JSX } from 'react';
import { useNavigate } from 'react-router-dom';

import { ConfirmButton } from '@/portal/components/ConfirmButton';
import { useDuplicate } from './reuseApi';

interface DuplicateButtonProps {
  emailId: number;
  /** The email's subject, which names what is being copied. */
  subject: string;
}

/** The button, its two ways to go ahead, and the move to the new draft. */
export function DuplicateButton({ emailId, subject }: DuplicateButtonProps): JSX.Element {
  const duplicate = useDuplicate(emailId);
  const navigate = useNavigate();

  const handleDuplicate = async (copyRecipients: boolean): Promise<void> => {
    const copy = await duplicate.mutateAsync({ copyRecipients });
    void navigate(`/bulk-email/compose/${copy.id}`);
  };

  return (
    <div className="stack-tight">
      <ConfirmButton
        label="Duplicate"
        choices={[
          { label: 'Copy the message', onChoose: () => handleDuplicate(false) },
          {
            label: 'Copy the message and the people',
            variant: 'secondary',
            onChoose: () => handleDuplicate(true),
          },
        ]}
      >
        <p>
          {`Start a new draft from ${subject === '' ? 'this email' : `"${subject}"`}. ` +
            'It keeps the subject, the message, and the type; this email stays as it is.'}
        </p>
      </ConfirmButton>
      {duplicate.error === null ? null : (
        <p className="field__error" role="alert">
          {duplicate.error.message}
        </p>
      )}
    </div>
  );
}
