/**
 * Recipient field tokens as text: how one is written, `{first_name|friend}`, what a
 * fallback may hold, and how a chip for one reads.  The rules mirror
 * `backend/apps/bulk_email/fields.py`, which fills the tokens in.
 */
import type { Node as ProseMirrorNode } from '@tiptap/pm/model';
import type { EditorState } from '@tiptap/pm/state';

import type { BulkEmailField } from '@/portal/api/types';

/** The node's name in the editor's schema. */
export const FIELD_TOKEN = 'fieldToken';

/**
 * A token: a lower-case name of letters, digits, and underscores in braces,
 * optionally followed by `|` and a fallback with no brace, bar, angle bracket, or
 * line break.  A brace doubled on either side is not a token.  This mirrors
 * `TOKEN_RE` in `backend/apps/bulk_email/fields.py`; the two must read alike.
 */
export const TOKEN_PATTERN = /(?<!\{)\{([a-z][a-z0-9_]*)(?:\|([^{}|<>\n]*))?\}(?!\})/g;

/** A character a fallback cannot hold, as `TOKEN_PATTERN` refuses it. */
const FALLBACK_REFUSED = /[{}|<>\n]/;

/**
 * Whitespace the server's plain-text part would read differently from the HTML:
 * anything but a single plain space.  The plain text reads every run of whitespace
 * as one space, so a fallback holding two spaces, a tab, or a non-breaking space
 * would no longer match its HTML, and the server refuses it.
 */
const UNEVEN_WHITESPACE = /[^\S ]| {2}/;

/** Any run of whitespace, which a fallback from the panel holds as one space. */
const WHITESPACE_RUN = /\s+/g;

/** Why a fallback cannot be used: the words `fields.py` describes a fallback in. */
export const FALLBACK_ERROR =
  'What to show must be plain text: no brace, bar, angle bracket, or line break.';

/** Why a fallback of nothing but spaces cannot be used. */
export const FALLBACK_BLANK_ERROR = 'Write a word to show, or leave the box empty to show nothing.';

/** What a chip whose name the catalog does not have says when pointed at. */
export const UNKNOWN_FIELD_TITLE = 'Not one of the fields';

/** The words an unknown chip carries after its token, so it shows without a pointer. */
export const UNKNOWN_FIELD_FLAG = 'not a field';

/** A whole token and nothing else, for reading a chip's own element back. */
export const WHOLE_TOKEN = new RegExp(`^${TOKEN_PATTERN.source}$`);

/** A token's parts: the field's name and the fallback, `''` when there is none. */
export interface FieldTokenAttrs {
  name: string;
  fallback: string;
}

/** The token as it is written: `{name}` or `{name|fallback}`. */
export function tokenText({ name, fallback }: FieldTokenAttrs): string {
  return fallback === '' ? `{${name}}` : `{${name}|${fallback}}`;
}

/** Whether `fallback` can go in a token as it is. */
export function isFallbackAllowed(fallback: string): boolean {
  return !FALLBACK_REFUSED.test(fallback);
}

/**
 * Whether the server fills in a token with `fallback` as written: no whitespace but
 * single plain spaces.
 */
export function isFallbackEven(fallback: string): boolean {
  return !UNEVEN_WHITESPACE.test(fallback);
}

/**
 * `fallback` as a token can hold it: each run of whitespace one plain space, and none
 * at either end.  A fallback of nothing but whitespace comes back `''`.
 */
export function evenFallback(fallback: string): string {
  return fallback.replace(WHITESPACE_RUN, ' ').trim();
}

/** How a chip reads: its label and fallback, or, for an unknown name, its token. */
export interface ChipText {
  label: string;
  fallback: string;
  isUnknown: boolean;
}

/**
 * How the chip for `attrs` reads given the catalog `labels` (token to label).
 *
 * While the catalog is still loading (`labels` is `null`) the name is shown made
 * readable, `first_name` as "first name".  A name the catalog does not have shows
 * the token itself, so the server's refusal of `{nickname}` names what the sender
 * sees.
 */
export function chipText(
  attrs: FieldTokenAttrs,
  labels: ReadonlyMap<string, string> | null,
): ChipText {
  if (labels === null) {
    return { label: attrs.name.replaceAll('_', ' '), fallback: attrs.fallback, isUnknown: false };
  }
  const label = labels.get(attrs.name);
  if (label === undefined) return { label: tokenText(attrs), fallback: '', isUnknown: true };
  return { label, fallback: attrs.fallback, isUnknown: false };
}

/**
 * The field catalog one editor's chips read their labels from.
 *
 * The editor's schema is built once, but the catalog arrives later, so the chips
 * subscribe and draw themselves again when `set` is called.
 */
export class FieldCatalog {
  #labels: ReadonlyMap<string, string> | null = null;
  readonly #listeners = new Set<() => void>();

  /** Token to label, or `null` while the catalog is still loading. */
  get labels(): ReadonlyMap<string, string> | null {
    return this.#labels;
  }

  /** Takes the catalog, `undefined` while it loads, and redraws every chip. */
  set(fields: readonly BulkEmailField[] | undefined): void {
    this.#labels =
      fields === undefined ? null : new Map(fields.map((field) => [field.token, field.label]));
    this.#listeners.forEach((listener) => listener());
  }

  /** Calls `listener` whenever the catalog changes; returns the unsubscribe. */
  subscribe(listener: () => void): () => void {
    this.#listeners.add(listener);
    return () => {
      this.#listeners.delete(listener);
    };
  }
}

/** The attributes of a `fieldToken` node. */
export function fieldAttrs(node: ProseMirrorNode): FieldTokenAttrs {
  return node.attrs as FieldTokenAttrs;
}

/** The node at `pos` when it is a chip, else `null`. */
export function chipAt(state: EditorState, pos: number): ProseMirrorNode | null {
  const node = state.doc.nodeAt(pos);
  return node?.type.name === FIELD_TOKEN ? node : null;
}
