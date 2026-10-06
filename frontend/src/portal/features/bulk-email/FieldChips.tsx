/**
 * Recipient fields shown as the compose editor's chips where a message is read as it
 * was written: a subject in the Drafts, Sent, Templates, and Callouts lists, and the
 * subject and message on the Sent detail page.  A chip reads as it does in the
 * editor, *First name, or friend*, and cannot be changed.  A recipient's own copy,
 * the preview, and a test email show the values filled in instead.
 */
import { useMemo } from 'react';
import type { JSX } from 'react';

import { TOKEN_PATTERN, UNKNOWN_FIELD_FLAG, chipText } from '@/portal/components/richTextTokens';
import './field-chips.css';
import { useBulkEmailFields } from './richTextApi';

/** Token to label from the field catalog, or `null` while it loads. */
export function useFieldLabels(): ReadonlyMap<string, string> | null {
  const fields = useBulkEmailFields();
  return useMemo(
    () =>
      fields.data === undefined
        ? null
        : new Map(fields.data.map((field) => [field.token, field.label])),
    [fields.data],
  );
}

/** One piece of a text, from its offset `at`: plain words, or a token's name and fallback. */
type Piece = { at: number } & ({ text: string } | { name: string; fallback: string });

/** `text` cut into its plain words and its tokens, in order. */
function pieces(text: string): Piece[] {
  const out: Piece[] = [];
  let at = 0;
  for (const match of text.matchAll(TOKEN_PATTERN)) {
    if (match.index > at) out.push({ at, text: text.slice(at, match.index) });
    out.push({ at: match.index, name: match[1] ?? '', fallback: match[2] ?? '' });
    at = match.index + match[0].length;
  }
  if (at < text.length) out.push({ at, text: text.slice(at) });
  return out;
}

/**
 * `text`, such as a subject, with each recipient field token in it shown as a
 * read-only chip: *Hello First name, or friend*.
 */
export function FieldText({ text }: { text: string }): JSX.Element {
  // Words without a field need no catalog, so a list of them asks for none.
  if (pieces(text).every((piece) => 'text' in piece)) return <>{text}</>;
  return <ChipText text={text} />;
}

/** `text` with its tokens as chips, their labels from the field catalog. */
function ChipText({ text }: { text: string }): JSX.Element {
  const labels = useFieldLabels();
  return (
    <>
      {pieces(text).map((piece) =>
        'text' in piece ? (
          piece.text
        ) : (
          <FieldChip key={piece.at} name={piece.name} fallback={piece.fallback} labels={labels} />
        ),
      )}
    </>
  );
}

interface FieldChipProps {
  name: string;
  fallback: string;
  labels: ReadonlyMap<string, string> | null;
}

/** One read-only chip, worded as the editor's (`chipText`). */
function FieldChip({ name, fallback, labels }: FieldChipProps): JSX.Element {
  const chip = chipText({ name, fallback }, labels);
  const className = chip.isUnknown
    ? 'rich-text__field field-chip rich-text__field--unknown'
    : 'rich-text__field field-chip';
  if (chip.isUnknown) {
    return (
      <span className={className}>
        {chip.label} <span className="rich-text__field-flag">{UNKNOWN_FIELD_FLAG}</span>
      </span>
    );
  }
  return (
    <span className={className}>
      {chip.label}
      {chip.fallback === '' ? null : (
        <>
          , or <em>{chip.fallback}</em>
        </>
      )}
    </span>
  );
}

/** The style a chip has inside the email's frame, which the portal's styles do not reach. */
const FRAME_CHIP_STYLE =
  '<style>.field-chip{padding:0 .25em;border:1px solid #8a8f98;border-radius:4px;' +
  'background:#eaf0fb;color:#1f2933;font-style:normal}</style>';

/** The elements whose text is never a message's words. */
const NOT_WORDS = new Set(['STYLE', 'SCRIPT', 'TITLE']);

/**
 * The whole HTML email `html` with each recipient field token in its words drawn as a
 * chip (`labels` names them, as `useFieldLabels` answers), and the chip's style put at
 * its head, for showing in `EmailFrame`.  Tokens in a style, a script, an attribute, or
 * a link's address are left as they are, and an email with none in its words comes
 * back unchanged.
 */
export function withFrameChips(html: string, labels: ReadonlyMap<string, string> | null): string {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT);
  const texts: Text[] = [];
  for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
    if (node instanceof Text && !NOT_WORDS.has(node.parentElement?.tagName ?? '')) {
      if (pieces(node.data).some((piece) => !('text' in piece))) texts.push(node);
    }
  }
  if (texts.length === 0) return html;
  texts.forEach((node) => drawChips(node, labels));
  doc.head.insertAdjacentHTML('afterbegin', FRAME_CHIP_STYLE);
  const doctype = doc.doctype === null ? '' : '<!DOCTYPE html>';
  return `${doctype}${doc.documentElement.outerHTML}`;
}

/** Replaces the text `node` with its words and a chip for each token in it. */
function drawChips(node: Text, labels: ReadonlyMap<string, string> | null): void {
  const parts = pieces(node.data);
  const doc = node.ownerDocument;
  const nodes = parts.map((piece) => {
    if ('text' in piece) return doc.createTextNode(piece.text);
    const chip = chipText(piece, labels);
    const span = doc.createElement('span');
    span.className = 'field-chip';
    if (chip.isUnknown || chip.fallback === '') {
      span.textContent = chip.isUnknown ? `${chip.label} ${UNKNOWN_FIELD_FLAG}` : chip.label;
      return span;
    }
    const emphasis = doc.createElement('em');
    emphasis.textContent = chip.fallback;
    span.append(`${chip.label}, or `, emphasis);
    return span;
  });
  node.replaceWith(...nodes);
}
