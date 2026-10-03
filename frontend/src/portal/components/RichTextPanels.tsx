/**
 * The two small panels `RichTextEditor` opens under its toolbar: one asks for a
 * link's address, the other for an uploaded image's description.
 *
 * Each panel takes the focus when it opens, closes on **Cancel** or on Escape in
 * its text box, and
 * says what is wrong in words when it cannot finish.
 */
import { useEffect, useRef, useState } from 'react';
import type { JSX, KeyboardEvent, ReactNode, RefObject } from 'react';

import { Button } from './Button';
import { Field } from './Field';
import { linkAddress } from './richText';

/** Why the address box cannot become a link. */
export const LINK_ADDRESS_ERROR =
  'Write a web address, such as caldart.org/events, or an email address.';

/** Why an image cannot go in without a description. */
export const IMAGE_ALT_ERROR = 'Describe the image before putting it in.';

interface PanelProps {
  /** The panel's accessible name. */
  label: string;
  children: ReactNode;
}

/** The frame both panels share: a labeled section under the toolbar. */
function Panel({ label, children }: PanelProps): JSX.Element {
  return (
    <section className="rich-text__panel stack-tight" aria-label={label}>
      {children}
    </section>
  );
}

/**
 * The key handler for a panel's text box: Enter does `onEnter` and Escape
 * `onEscape`.  The editor usually sits in a form, and Enter here must never
 * submit it.
 */
function panelKeys(
  onEnter: () => void,
  onEscape: () => void,
): (event: KeyboardEvent<HTMLInputElement>) => void {
  return (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      onEnter();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      onEscape();
    }
  };
}

/** Focuses the element `ref` points at once, when the panel mounts. */
function useFocusOnMount<T extends HTMLElement>(): RefObject<T | null> {
  const ref = useRef<T>(null);
  useEffect(() => {
    ref.current?.focus();
  }, []);
  return ref;
}

export interface LinkPanelProps {
  /** The address the selected link already goes to, `''` for a new link. */
  initialAddress: string;
  /** Whether the selection is already a link, which offers **Remove link**. */
  isEditing: boolean;
  /** Links the selection to `href`, an address `linkAddress` accepted. */
  onApply: (href: string) => void;
  /** Takes the link off the selection. */
  onRemove: () => void;
  onCancel: () => void;
}

/**
 * Asks for the address a link goes to.
 *
 * The address is read by `linkAddress`, so a sender can type `caldart.org` or an
 * email address without the scheme; text that cannot be a link is refused with
 * `LINK_ADDRESS_ERROR` and the panel stays open.
 */
export function LinkPanel({
  initialAddress,
  isEditing,
  onApply,
  onRemove: handleRemove,
  onCancel: handleCancel,
}: LinkPanelProps): JSX.Element {
  const [typed, setTyped] = useState(initialAddress);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useFocusOnMount<HTMLInputElement>();

  const handleApply = (): void => {
    const href = linkAddress(typed);
    if (href === null) {
      setError(LINK_ADDRESS_ERROR);
      return;
    }
    onApply(href);
  };

  const handleKeyDown = panelKeys(handleApply, handleCancel);

  return (
    <Panel label="Link">
      <Field
        label="Web or email address"
        hint="Where the link goes, such as caldart.org/events."
        error={error}
      >
        {(props) => (
          <input
            {...props}
            ref={inputRef}
            type="text"
            inputMode="url"
            autoComplete="off"
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            onKeyDown={handleKeyDown}
          />
        )}
      </Field>
      <div className="cluster">
        <Button small onClick={handleApply}>
          {isEditing ? 'Save link' : 'Add link'}
        </Button>
        {isEditing ? (
          <Button small variant="secondary" onClick={handleRemove}>
            Remove link
          </Button>
        ) : null}
        <Button small variant="quiet" onClick={handleCancel}>
          Cancel
        </Button>
      </div>
    </Panel>
  );
}

/** Where an upload stands while its panel is open. */
export type UploadState =
  | { status: 'uploading' }
  | { status: 'failed'; message: string }
  | { status: 'ready'; url: string; width: number; height: number };

export interface ImagePanelProps {
  /** The name of the file being uploaded, to say which one. */
  fileName: string;
  upload: UploadState;
  /** Puts the uploaded image in with the description `alt`, never blank. */
  onInsert: (alt: string) => void;
  onCancel: () => void;
}

/**
 * Asks for an uploaded image's description, and puts the image in.
 *
 * The description is required: many mail programs hide images until the reader
 * allows them, and the description is what stands in.  **Put image in** waits for
 * the upload; a failed upload says why and offers only **Cancel**.
 */
export function ImagePanel({
  fileName,
  upload,
  onInsert,
  onCancel: handleCancel,
}: ImagePanelProps): JSX.Element {
  const [alt, setAlt] = useState('');
  const [error, setError] = useState<string | null>(null);
  const inputRef = useFocusOnMount<HTMLInputElement>();

  const handleInsert = (): void => {
    if (alt.trim() === '') {
      setError(IMAGE_ALT_ERROR);
      return;
    }
    onInsert(alt.trim());
  };

  const handleKeyDown = panelKeys(() => {
    if (upload.status === 'ready') handleInsert();
  }, handleCancel);

  return (
    <Panel label="Image">
      <p className="rich-text__status" role="status">
        {upload.status === 'uploading' ? `Uploading ${fileName}…` : null}
        {upload.status === 'ready' ? `${fileName} is uploaded.` : null}
      </p>
      {upload.status === 'failed' ? (
        <p className="field__error" role="alert">
          {upload.message}
        </p>
      ) : (
        <Field
          label="Describe the image"
          hint="Many mail programs hide images until the reader allows them; this description stands in, and is read aloud to people who cannot see it."
          error={error}
          required
        >
          {(props) => (
            <input
              {...props}
              ref={inputRef}
              type="text"
              value={alt}
              onChange={(event) => setAlt(event.target.value)}
              onKeyDown={handleKeyDown}
            />
          )}
        </Field>
      )}
      <div className="cluster">
        {upload.status === 'failed' ? null : (
          <Button small disabled={upload.status !== 'ready'} onClick={handleInsert}>
            Put image in
          </Button>
        )}
        <Button small variant="quiet" onClick={handleCancel}>
          Cancel
        </Button>
      </div>
    </Panel>
  );
}
