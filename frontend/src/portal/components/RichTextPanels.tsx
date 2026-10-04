/**
 * The small panels `RichTextEditor` opens under its toolbar: one asks for a link's
 * address, one for an uploaded image's description, and one for what a recipient
 * field's chip shows for a person with no value.
 *
 * Each panel takes the focus when it opens, closes on **Cancel** or on Escape
 * anywhere inside it, and says what is wrong in words when it cannot finish.
 */
import { useEffect, useRef, useState } from 'react';
import type { JSX, KeyboardEvent, ReactNode, RefObject } from 'react';

import { Button } from './Button';
import { Field } from './Field';
import { linkAddress } from './richText';
import { FALLBACK_ERROR, isFallbackAllowed } from './richTextField';

/** Why the address box cannot become a link. */
export const LINK_ADDRESS_ERROR =
  'Write a web address, such as caldart.org/events, or an email address.';

/** Why an image cannot go in without a description. */
export const IMAGE_ALT_ERROR = 'Describe the image before putting it in.';

interface PanelProps {
  /** The panel's accessible name. */
  label: string;
  /** Closes the panel, on Escape anywhere inside it. */
  onCancel: () => void;
  children: ReactNode;
}

/**
 * The frame both panels share: a labeled section under the toolbar that closes on
 * Escape wherever the focus is inside it, a text box or a button alike.
 */
function Panel({ label, onCancel, children }: PanelProps): JSX.Element {
  const sectionRef = useRef<HTMLElement>(null);
  const cancelRef = useRef(onCancel);
  useEffect(() => {
    cancelRef.current = onCancel;
  }, [onCancel]);

  // A native listener: the section is not itself a control, so it carries no
  // React key handler, but a key pressed on any control inside bubbles to it.
  useEffect(() => {
    const section = sectionRef.current;
    if (section === null) return undefined;
    const handleKeyDown = (event: globalThis.KeyboardEvent): void => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      cancelRef.current();
    };
    section.addEventListener('keydown', handleKeyDown);
    return () => section.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <section ref={sectionRef} className="rich-text__panel stack-tight" aria-label={label}>
      {children}
    </section>
  );
}

/**
 * The key handler for a panel's text box: Enter does `onEnter`.  The editor
 * usually sits in a form, and Enter here must never submit it.
 */
function enterKey(onEnter: () => void): (event: KeyboardEvent<HTMLInputElement>) => void {
  return (event) => {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    onEnter();
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

  const handleKeyDown = enterKey(handleApply);

  return (
    <Panel label="Link" onCancel={handleCancel}>
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

export interface FieldPanelProps {
  /** The field's label, such as "First name", which names the panel. */
  label: string;
  /** The chip's fallback, `''` when it has none. */
  initialFallback: string;
  /** Sets the fallback to `fallback`, which `isFallbackAllowed` accepted. */
  onApply: (fallback: string) => void;
  /** Takes the fallback off. */
  onClear: () => void;
  onCancel: () => void;
}

/**
 * Asks what a field's chip shows for a person with no value, its fallback.
 *
 * **Apply** sets it, and **Clear**, offered once a fallback is set, takes it off.
 * Text holding a brace, a bar, an angle bracket, or a line break cannot be part of
 * a token, so it is refused with `FALLBACK_ERROR` and the panel stays open.
 */
export function FieldPanel({
  label,
  initialFallback,
  onApply,
  onClear: handleClear,
  onCancel: handleCancel,
}: FieldPanelProps): JSX.Element {
  const [fallback, setFallback] = useState(initialFallback);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useFocusOnMount<HTMLInputElement>();

  const handleApply = (): void => {
    if (!isFallbackAllowed(fallback)) {
      setError(FALLBACK_ERROR);
      return;
    }
    onApply(fallback);
  };

  const handleKeyDown = enterKey(handleApply);

  return (
    <Panel label={`${label} field`} onCancel={handleCancel}>
      <Field
        label="If the person has no value, show"
        hint={`What stands in for ${label}, such as friend. Leave it empty to show nothing.`}
        error={error}
      >
        {(props) => (
          <input
            {...props}
            ref={inputRef}
            type="text"
            autoComplete="off"
            value={fallback}
            onChange={(event) => setFallback(event.target.value)}
            onKeyDown={handleKeyDown}
          />
        )}
      </Field>
      <div className="cluster">
        <Button small onClick={handleApply}>
          Apply
        </Button>
        {initialFallback === '' ? null : (
          <Button small variant="secondary" onClick={handleClear}>
            Clear
          </Button>
        )}
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
 * the upload; a failed upload says why, offers only **Cancel**, and moves the focus
 * to it, since the description box that held the focus is gone.
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
  const cancelRef = useRef<HTMLButtonElement>(null);
  const hasFailed = upload.status === 'failed';

  useEffect(() => {
    if (hasFailed) cancelRef.current?.focus();
  }, [hasFailed]);

  const handleInsert = (): void => {
    if (alt.trim() === '') {
      setError(IMAGE_ALT_ERROR);
      return;
    }
    onInsert(alt.trim());
  };

  const handleKeyDown = enterKey(() => {
    if (upload.status === 'ready') handleInsert();
  });

  return (
    <Panel label="Image" onCancel={handleCancel}>
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
        <Button ref={cancelRef} small variant="quiet" onClick={handleCancel}>
          Cancel
        </Button>
      </div>
    </Panel>
  );
}
