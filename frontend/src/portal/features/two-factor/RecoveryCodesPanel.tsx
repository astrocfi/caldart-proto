import { useState } from 'react';
import type { JSX } from 'react';

import { Button } from '@/portal/components/Button';
import './two-factor.css';

/** The file the codes download as. */
export const CODES_FILENAME = 'caldart-backup-codes.txt';

/** How long the download's object URL is kept before it is revoked. */
const DOWNLOAD_URL_LIFETIME_MS = 1000;

export interface RecoveryCodesPanelProps {
  codes: string[];
  /** Called when the person says they saved the codes. */
  onDone: () => void;
  /** The button that moves on: `I saved these` unless a screen says otherwise. */
  doneLabel?: string;
}

/** The codes as the downloaded file holds them: a line about them, then one per line. */
export function codesText(codes: string[]): string {
  return [
    'CalDART backup codes. Each code works once, in place of a code from your phone.',
    '',
    ...codes,
    '',
  ].join('\n');
}

/** Hand the browser `text` as a file named `filename` to save. */
function downloadText(filename: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  // Revoked once the browser has had a turn to start the download it was asked for.
  setTimeout(() => URL.revokeObjectURL(url), DOWNLOAD_URL_LIFETIME_MS);
}

/**
 * A fresh set of backup codes, shown once: the list, **Copy** and **Download** buttons,
 * and the button that moves on.  The codes are not shown again anywhere, so the panel
 * says so.
 */
export function RecoveryCodesPanel({
  codes,
  onDone: handleDone,
  doneLabel = 'I saved these',
}: RecoveryCodesPanelProps): JSX.Element {
  const [copied, setCopied] = useState<'yes' | 'failed' | null>(null);

  const handleCopy = () => {
    navigator.clipboard.writeText(codes.join('\n')).then(
      () => setCopied('yes'),
      () => setCopied('failed'),
    );
  };

  return (
    <div className="stack recovery-codes">
      <p>
        Save these backup codes somewhere safe, away from your phone. Each one signs you in once if
        you lose your phone. They are not shown again.
      </p>
      <ol className="recovery-codes__list" aria-label="Backup codes">
        {codes.map((code) => (
          <li key={code}>
            <code>{code}</code>
          </li>
        ))}
      </ol>
      <div className="cluster">
        <Button variant="secondary" onClick={handleCopy}>
          Copy
        </Button>
        <Button variant="secondary" onClick={() => downloadText(CODES_FILENAME, codesText(codes))}>
          Download as .txt
        </Button>
        {copied === 'yes' ? (
          <span role="status" className="muted">
            Copied.
          </span>
        ) : null}
        {copied === 'failed' ? (
          <span role="alert" className="field__error">
            Your browser did not allow copying. Download the codes instead.
          </span>
        ) : null}
      </div>
      <Button onClick={handleDone}>{doneLabel}</Button>
    </div>
  );
}
