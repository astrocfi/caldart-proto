/**
 * `/admin/bulk-email`: CalDART management's screen for emailing everybody a
 * filter selects.
 *
 * It reads top to bottom.  The member list's own filters choose the people, the
 * subject and the message come next, and **Preview recipients** lists who would
 * be sent a copy and who is skipped and why, sending nothing; **Download list**
 * saves that list.  **Send to N people** asks first, then sends, and the result
 * for each person replaces the preview.  The history of past sends sits below.
 *
 * Changing a filter puts the preview away, since it no longer says who the email
 * would reach.  The send rebuilds the list on the server, so somebody who joined
 * the filters after the preview is sent a copy too.
 */
import { useMemo, useState } from 'react';
import type { FormEvent, JSX } from 'react';

import { useDarts } from '@/portal/api/queries';
import { ApiError } from '@/portal/api/client';
import type { BulkEmailMessage } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { ConfirmButton } from '@/portal/components/ConfirmButton';
import { Field } from '@/portal/components/Field';
import { FilterBar } from '@/portal/components/FilterBar';
import { Page } from '@/portal/components/Page';
import { RunActionsTable } from '@/portal/components/RunActionsTable';
import { listFilters, REPORTS } from '@/portal/reports/definitions';
import type { FilterValues } from '@/portal/reports/types';
import { givenFilters, previewCsvUrl, usePreviewBulkEmail, useSendBulkEmail } from './api';
import { BulkEmailHistory } from './BulkEmailHistory';
import { BulkEmailResults } from './BulkEmailResults';
import { previewActions, previewSummary, resultLabel, sendLabel } from './results';

/** The member list's filters, less any only a subscription offers. */
const FILTER_FIELDS = listFilters(REPORTS.members);

/** The longest subject the server accepts. */
const SUBJECT_MAX_LENGTH = 200;

/** The longest message the server accepts. */
const BODY_MAX_LENGTH = 20000;

/** What the screen says when a request fails without a message of its own. */
const FALLBACK_ERROR = 'That did not work. Try again.';

/** The messages a refusal carries, by field, plus one for the whole form. */
interface FormErrors {
  subject?: string;
  body?: string;
  general?: string;
}

/**
 * A refusal's messages, by field.  A complaint about the filters, such as
 * *Nobody matches these filters.*, is the form's own message.
 */
function formErrors(error: unknown): FormErrors {
  if (!(error instanceof ApiError)) return { general: FALLBACK_ERROR };
  const fields = error.fieldErrors;
  const isFieldError = fields.subject !== undefined || fields.body !== undefined;
  const general = fields.filters ?? (isFieldError ? undefined : error.message);
  return { subject: fields.subject, body: fields.body, general };
}

/** `/admin/bulk-email`: compose, preview, send, and the history. */
export function BulkEmailPage(): JSX.Element {
  const [filters, setFilters] = useState<FilterValues>({});
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');

  const darts = useDarts();
  const dartOptions = useMemo(
    () => ({
      dart: (darts.data ?? []).map((dart) => ({ value: String(dart.id), label: dart.name })),
    }),
    [darts.data],
  );

  const preview = usePreviewBulkEmail();
  const send = useSendBulkEmail();
  const message: BulkEmailMessage = { subject, body, filters: givenFilters(filters) };
  const failure = preview.error ?? send.error;
  const errors = failure === null ? {} : formErrors(failure);

  const handleFilterChange = (next: FilterValues): void => {
    setFilters(next);
    preview.reset();
  };

  const handlePreview = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    send.reset();
    preview.mutate(message);
  };

  const handleSend = async (): Promise<void> => {
    await send.mutateAsync(message);
    preview.reset();
  };

  return (
    <Page
      title="Bulk Email"
      eyebrow="Administration"
      lede="Write to every member and friend a filter selects. Preview the list, then send."
    >
      <Card eyebrow="Compose" title="Who and what">
        <FilterBar
          fields={FILTER_FIELDS}
          values={filters}
          onChange={handleFilterChange}
          options={dartOptions}
          label="Choose the recipients"
        />
        <form className="stack" onSubmit={handlePreview} noValidate>
          <Field label="Subject" error={errors.subject} required>
            {(field) => (
              <input
                {...field}
                type="text"
                maxLength={SUBJECT_MAX_LENGTH}
                value={subject}
                onChange={(event) => setSubject(event.target.value)}
              />
            )}
          </Field>
          <Field
            label="Message"
            hint="Plain text. Leave a blank line between paragraphs."
            error={errors.body}
            required
          >
            {(field) => (
              <textarea
                {...field}
                rows={10}
                maxLength={BODY_MAX_LENGTH}
                value={body}
                onChange={(event) => setBody(event.target.value)}
              />
            )}
          </Field>
          <div className="cluster">
            <Button type="submit" disabled={preview.isPending}>
              {preview.isPending ? 'Previewing…' : 'Preview recipients'}
            </Button>
          </div>
        </form>

        {errors.general === undefined ? null : (
          <p className="field__error" role="alert">
            {errors.general}
          </p>
        )}

        {preview.data ? (
          <RunActionsTable
            actions={previewActions(preview.data)}
            dryRun={true}
            kindLabel={resultLabel}
            detailHeader="Reason"
            hasWhenAndAmount={false}
            summary={
              <>
                <p role="status">{previewSummary(preview.data)}</p>
                <p>
                  <a href={previewCsvUrl(filters)} download>
                    Download list
                  </a>
                </p>
              </>
            }
          />
        ) : null}

        {preview.data && preview.data.count > 0 ? (
          <ConfirmButton
            label={sendLabel(preview.data.count)}
            variant="primary"
            choices={[{ label: 'Send now', onChoose: handleSend }]}
          >
            <p>
              This sends <strong>{subject}</strong> to {preview.data.count}{' '}
              {preview.data.count === 1 ? 'person' : 'people'} now. A sent email cannot be called
              back.
            </p>
          </ConfirmButton>
        ) : null}

        {send.data ? <BulkEmailResults sent={send.data} /> : null}
      </Card>

      <BulkEmailHistory />
    </Page>
  );
}
