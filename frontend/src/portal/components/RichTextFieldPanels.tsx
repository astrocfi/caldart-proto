/**
 * The panels a recipient field's chip opens under the editor's toolbar: one sets
 * what a field shows for a person with no value, the other offers the ways out of a
 * chip whose name is not one of the fields.
 *
 * Each panel is about one chip.  It follows that chip while the message changes
 * around it, closes if the chip is changed or taken out from under it, and, however
 * it closes, leaves a plain cursor just after the chip so the next key typed goes
 * in beside it rather than over it.
 */
import type { Transaction } from '@tiptap/pm/state';
import type { Editor } from '@tiptap/react';
import { useEffect, useRef, useState } from 'react';
import type { JSX } from 'react';

import type { BulkEmailField } from '@/portal/api/types';

import { Button } from './Button';
import { Field } from './Field';
import {
  fieldToWords,
  placeCursorAfterField,
  removeField,
  renameField,
  setFieldFallback,
} from './richTextFieldCommands';
import { Panel, enterKey, useFocusOnMount } from './RichTextPanels';
import {
  FALLBACK_BLANK_ERROR,
  FALLBACK_ERROR,
  chipText,
  evenFallback,
  fieldAttrs,
  isFallbackAllowed,
  tokenText,
} from './richTextTokens';
import type { FieldTokenAttrs } from './richTextTokens';

export interface ChipPanelProps {
  editor: Editor;
  /** Where the chip sat when the panel opened. */
  pos: number;
  /** The chip as it was when the panel opened. */
  attrs: FieldTokenAttrs;
  /** The recipient fields, `undefined` while they load. */
  fields: BulkEmailField[] | undefined;
  /** Takes the panel away; the panel has already placed the cursor. */
  onClose: () => void;
}

/**
 * The panel for the chip `attrs` at `pos`: `UnknownFieldPanel` when `fields` has
 * loaded without its name, else `FieldPanel`.
 */
export function ChipPanel({ editor, pos, attrs, fields, onClose }: ChipPanelProps): JSX.Element {
  const posRef = useChipPosition(editor, pos, attrs, onClose);
  const labels = fields === undefined ? null : new Map(fields.map((f) => [f.token, f.label]));
  const { label } = chipText({ ...attrs, fallback: '' }, labels);

  const finish = (change: (at: number) => void): void => {
    onClose();
    change(posRef.current);
  };

  if (labels !== null && !labels.has(attrs.name)) {
    return (
      <UnknownFieldPanel
        token={tokenText(attrs)}
        fields={fields ?? []}
        onChoose={(name) => finish((at) => renameField(editor, at, attrs, name))}
        onWords={() => finish((at) => fieldToWords(editor, at, attrs))}
        onRemove={() => finish((at) => removeField(editor, at, attrs))}
        onCancel={() => finish((at) => placeCursorAfterField(editor, at))}
      />
    );
  }
  return (
    <FieldPanel
      label={label}
      initialFallback={attrs.fallback}
      onApply={(fallback) => finish((at) => setFieldFallback(editor, at, attrs, fallback))}
      onClear={() => finish((at) => setFieldFallback(editor, at, attrs, ''))}
      onCancel={() => finish((at) => placeCursorAfterField(editor, at))}
    />
  );
}

/**
 * Where the chip `attrs`, first at `pos`, is now: followed through every change to
 * the message.  `onGone` is called once a change takes the chip out or alters it.
 */
function useChipPosition(
  editor: Editor,
  pos: number,
  attrs: FieldTokenAttrs,
  onGone: () => void,
): { current: number } {
  const posRef = useRef(pos);
  const goneRef = useRef(onGone);
  useEffect(() => {
    goneRef.current = onGone;
  }, [onGone]);

  useEffect(() => {
    const handleTransaction = ({
      transaction,
      appendedTransactions,
    }: {
      transaction: Transaction;
      appendedTransactions: Transaction[];
    }): void => {
      const steps = [transaction, ...appendedTransactions].filter((tr) => tr.docChanged);
      if (steps.length === 0) return;
      let at = posRef.current;
      for (const tr of steps) {
        const mapped = tr.mapping.mapResult(at, 1);
        if (mapped.deleted) {
          goneRef.current();
          return;
        }
        at = mapped.pos;
      }
      const node = editor.state.doc.nodeAt(at);
      const now = node === null ? null : fieldAttrs(node);
      if (now?.name !== attrs.name || now.fallback !== attrs.fallback) {
        goneRef.current();
        return;
      }
      posRef.current = at;
    };
    editor.on('transaction', handleTransaction);
    return () => {
      editor.off('transaction', handleTransaction);
    };
  }, [editor, attrs]);

  return posRef;
}

/**
 * How a sentence names a field: "first name" for "First name", but "DART" as it is,
 * since lower-casing an abbreviation would misspell it.
 */
export function fieldPhrase(label: string): string {
  const [first = '', second = ''] = label;
  return second === second.toLowerCase() ? first.toLowerCase() + label.slice(1) : label;
}

export interface FieldPanelProps {
  /** The field's label, such as "First name", which titles the panel. */
  label: string;
  /** The chip's fallback, `''` when it has none. */
  initialFallback: string;
  /**
   * Sets the fallback to `fallback`, which `isFallbackAllowed` accepted and
   * `evenFallback` evened out; `''` when the box was left empty.
   */
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
 * a token, so it is refused with `FALLBACK_ERROR` and the panel stays open; so is
 * text of nothing but spaces, with `FALLBACK_BLANK_ERROR`.  Any other run of
 * whitespace goes in as one space and none at either end, the only spacing the
 * server fills in alike in both parts of a copy.
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
    const even = evenFallback(fallback);
    if (even === '' && fallback !== '') {
      setError(FALLBACK_BLANK_ERROR);
      return;
    }
    onApply(even);
  };

  const handleKeyDown = enterKey(handleApply);

  return (
    <Panel label={`${label} field`} onCancel={handleCancel}>
      <p className="rich-text__panel-title">{label}</p>
      <Field
        label={`If we don't have their ${fieldPhrase(label)}, show`}
        hint="Such as friend. Leave it empty to show nothing."
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

export interface UnknownFieldPanelProps {
  /** The chip's token as written, such as `{nickname}`. */
  token: string;
  /** The fields **Choose a field** offers. */
  fields: BulkEmailField[];
  /** Makes the chip the field named `name`. */
  onChoose: (name: string) => void;
  /** Puts the chip back as words, its braces taken out. */
  onWords: () => void;
  /** Takes the chip out. */
  onRemove: () => void;
  onCancel: () => void;
}

/**
 * Says a chip is not one of the fields and offers the ways out: **Choose a field**
 * lists the fields to make it one of them, **Turn into words** takes its braces out,
 * and **Remove** takes it out.
 */
export function UnknownFieldPanel({
  token,
  fields,
  onChoose,
  onWords: handleWords,
  onRemove: handleRemove,
  onCancel: handleCancel,
}: UnknownFieldPanelProps): JSX.Element {
  const [isChoosing, setIsChoosing] = useState(false);
  const chooseRef = useFocusOnMount<HTMLButtonElement>();

  return (
    <Panel label="Unknown field" onCancel={handleCancel}>
      <p className="rich-text__panel-title">{token} is not one of the fields.</p>
      <div className="cluster">
        <Button
          ref={chooseRef}
          small
          aria-expanded={isChoosing}
          onClick={() => setIsChoosing((open) => !open)}
        >
          Choose a field
        </Button>
        <Button small variant="secondary" onClick={handleWords}>
          Turn into words
        </Button>
        <Button small variant="secondary" onClick={handleRemove}>
          Remove
        </Button>
        <Button small variant="quiet" onClick={handleCancel}>
          Cancel
        </Button>
      </div>
      {isChoosing ? (
        <ul className="rich-text__field-choices" aria-label="Fields">
          {fields.map((field) => (
            <li key={field.token}>
              <button
                type="button"
                className="rich-text__field-choice"
                onClick={() => onChoose(field.token)}
              >
                {field.label}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </Panel>
  );
}
