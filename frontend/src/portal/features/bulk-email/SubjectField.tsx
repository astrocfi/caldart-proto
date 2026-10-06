/**
 * The subject box of the compose screen and the template form, with its own
 * **Insert field** beside it while it can be written.
 */
import type { JSX, RefObject } from 'react';

import { Field } from '@/portal/components/Field';
import { SUBJECT_HINT } from './fieldText';
import { SubjectFieldMenu } from './InsertFieldMenu';

/** The longest subject the server accepts. */
const SUBJECT_MAX_LENGTH = 200;

interface SubjectFieldProps {
  subjectRef: RefObject<HTMLInputElement | null>;
  subject: string;
  onSubjectChange: (subject: string) => void;
  /** The server's complaint about the subject, if it refused it. */
  error: string | undefined;
  /** False while the subject is shown rather than changed: no Insert field then. */
  isEditable: boolean;
}

/** The labeled subject input, with **Insert field** on its right while editable. */
export function SubjectField({
  subjectRef,
  subject,
  onSubjectChange: handleSubjectChange,
  error,
  isEditable,
}: SubjectFieldProps): JSX.Element {
  return (
    <Field label="Subject" error={error} hint={SUBJECT_HINT}>
      {(field) => (
        <div className="insert-field__subject">
          <input
            {...field}
            ref={subjectRef}
            type="text"
            maxLength={SUBJECT_MAX_LENGTH}
            value={subject}
            onChange={(event) => handleSubjectChange(event.target.value)}
          />
          {isEditable ? (
            <SubjectFieldMenu subjectRef={subjectRef} onSubjectChange={handleSubjectChange} />
          ) : null}
        </div>
      )}
    </Field>
  );
}
