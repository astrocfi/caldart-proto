/**
 * The editor's view of a recipient field: a `fieldToken` node that shows a token
 * such as `{first_name|friend}` as one chip, "First name, or *friend*".
 *
 * The chip is only how the editor shows the token.  It is written back out as the
 * token's own text, so the HTML the editor reports, and the server reads, is the
 * same as if the token had been typed: `getHTML()`, a copy to the clipboard, and
 * `getText()` all carry `{first_name|friend}`.  Token text that reaches the editor
 * any other way, a draft loading, a template applied, a paste, or typing, becomes a
 * chip as soon as it is complete; typed text waits until the cursor has left it, so
 * a sender can still finish writing `{first_name|friend}` or turn it into `{{x}}`.
 * A chip a brace typed beside it turns into no token, `{{first_name}`, goes back to
 * text, so a chip always stands for a token the server will fill in.
 */
import { Node } from '@tiptap/react';
import type { Editor } from '@tiptap/react';
import { DOMSerializer } from '@tiptap/pm/model';
import type { Fragment, Mark, Node as ProseMirrorNode, NodeType, Schema } from '@tiptap/pm/model';
import { NodeSelection, Plugin, PluginKey } from '@tiptap/pm/state';
import type { EditorState, Transaction } from '@tiptap/pm/state';

import type { BulkEmailField } from '@/portal/api/types';

/** The node's name in the editor's schema. */
export const FIELD_TOKEN = 'fieldToken';

/**
 * A token: a lower-case name of letters, digits, and underscores in braces,
 * optionally followed by `|` and a fallback with no brace, bar, angle bracket, or
 * line break.  A brace doubled on either side is not a token.  This mirrors
 * `TOKEN_RE` in `backend/apps/bulk_email/fields.py`; the two must read alike.
 */
const TOKEN_PATTERN = /(?<!\{)\{([a-z][a-z0-9_]*)(?:\|([^{}|<>\n]*))?\}(?!\})/g;

/** A character a fallback cannot hold, as `TOKEN_PATTERN` refuses it. */
const FALLBACK_REFUSED = /[{}|<>\n]/;

/** Why a fallback cannot be used: the words `fields.py` describes a fallback in. */
export const FALLBACK_ERROR =
  'What to show must be plain text: no brace, bar, angle bracket, or line break.';

/** What a chip whose name the catalog does not have says when pointed at. */
export const UNKNOWN_FIELD_TITLE = 'Not one of the fields';

/** A whole token and nothing else, for reading a chip's own element back. */
const WHOLE_TOKEN = new RegExp(`^${TOKEN_PATTERN.source}$`);

/** Marks the element a chip is first written as, before `TokenSerializer` unwraps it. */
const TOKEN_ATTRIBUTE = 'data-field-token';

/** Stands in for an image or a line break when a paragraph is read as text. */
const OBJECT_CHARACTER = '\uFFFC';

/** Marks a transaction whose token text should all become chips, cursor or not. */
const CONVERT_ALL = 'convertAll';

/** What the browser marks a paste or a drop with, which converts at once too. */
const WHOLESALE_EVENTS = new Set(['paste', 'drop']);

const PLUGIN_KEY = new PluginKey('fieldToken');

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

export interface FieldTokenOptions {
  /** Where the chips read their labels. */
  catalog: FieldCatalog;
  /** Asks for the fallback of the chip at `pos`: a click on it, or Enter or Space. */
  onOpen: (pos: number, attrs: FieldTokenAttrs) => void;
}

/** A token written as text, ready to become a chip. */
interface TokenRange {
  from: number;
  to: number;
  attrs: FieldTokenAttrs;
  marks: readonly Mark[];
}

/** A chip whose neighbors make its token text no token, at `pos`. */
interface BrokenChip {
  pos: number;
  node: ProseMirrorNode;
}

/** What a document's tokens need: text to become chips, chips to become text. */
interface TokenScan {
  toChip: TokenRange[];
  toText: BrokenChip[];
}

/** One child of a paragraph and where it sits in the paragraph's text. */
interface Segment {
  start: number;
  end: number;
  pos: number;
  node: ProseMirrorNode;
}

/** The attributes of a `fieldToken` node. */
export function fieldAttrs(node: ProseMirrorNode): FieldTokenAttrs {
  return node.attrs as FieldTokenAttrs;
}

/**
 * Reads every paragraph of `doc` as the server would read its HTML, each chip as its
 * token's text and an image or a line break as one object character, and answers
 * which token text should become a chip and which chip should become text.
 *
 * A token written as text becomes a chip only when all of it lies in one run of text
 * with the same styles: one split by bold or a link is left as text, which the server
 * refuses.  A chip becomes text again when a brace written beside it doubles one of
 * its own, `{` before it or `}` after it, since the server then reads no token there
 * either.
 */
function scanTokens(doc: ProseMirrorNode): TokenScan {
  const scan: TokenScan = { toChip: [], toText: [] };
  doc.descendants((block, blockPos) => {
    if (!block.isTextblock) return true;
    const segments: Segment[] = [];
    let text = '';
    block.forEach((child, offset) => {
      const start = text.length;
      if (child.isText) text += child.text ?? '';
      else if (child.type.name === FIELD_TOKEN) text += tokenText(fieldAttrs(child));
      else text += OBJECT_CHARACTER;
      segments.push({ start, end: text.length, pos: blockPos + 1 + offset, node: child });
    });
    const tokens = new Set<string>();
    for (const match of text.matchAll(TOKEN_PATTERN)) {
      const start = match.index;
      const end = start + match[0].length;
      tokens.add(`${start}:${end}`);
      const run = segments.find(
        (segment) => segment.node.isText && segment.start <= start && end <= segment.end,
      );
      if (run === undefined) continue;
      scan.toChip.push({
        from: run.pos + start - run.start,
        to: run.pos + end - run.start,
        attrs: { name: match[1] ?? '', fallback: match[2] ?? '' },
        marks: run.node.marks,
      });
    }
    for (const segment of segments) {
      if (segment.node.type.name !== FIELD_TOKEN) continue;
      if (!tokens.has(`${segment.start}:${segment.end}`)) {
        scan.toText.push({ pos: segment.pos, node: segment.node });
      }
    }
    return false;
  });
  return scan;
}

/**
 * Whether `transactions` put text in wholesale, a draft or a template loading or a
 * paste or a drop, so every token in it becomes a chip whether or not the cursor
 * is beside it.
 */
function isWholesale(transactions: readonly Transaction[]): boolean {
  return transactions.some(
    (tr) =>
      tr.getMeta(PLUGIN_KEY) === CONVERT_ALL ||
      tr.getMeta('preventUpdate') === true ||
      WHOLESALE_EVENTS.has(tr.getMeta('uiEvent') as string),
  );
}

/**
 * A transaction bringing the chips in `state` into line with its tokens, or `null`
 * when they already are.  With `spareCursor`, token text the selection touches stays
 * text: the sender may still be typing it.
 */
function convertTokens(
  state: EditorState,
  type: NodeType,
  spareCursor: boolean,
): Transaction | null {
  const { from, to } = state.selection;
  const scan = scanTokens(state.doc);
  const toChip = scan.toChip.filter(
    (range) => !(spareCursor && range.from <= to && from <= range.to),
  );
  if (toChip.length === 0 && scan.toText.length === 0) return null;
  const changes = [
    ...toChip.map((range) => ({
      from: range.from,
      to: range.to,
      node: type.create(range.attrs, null, range.marks),
    })),
    ...scan.toText.map(({ pos, node }) => ({
      from: pos,
      to: pos + node.nodeSize,
      node: state.schema.text(tokenText(fieldAttrs(node)), node.marks),
    })),
  ];
  const tr = state.tr;
  // From the end, so each earlier change's positions still hold.
  for (const change of changes.sort((a, b) => b.from - a.from)) {
    tr.replaceWith(change.from, change.to, change.node);
  }
  return tr;
}

/** Puts a chip for the field `name` in at the cursor, replacing any selection. */
export function insertFieldToken(editor: Editor, name: string): void {
  editor
    .chain()
    .focus()
    .command(({ tr, state }) => {
      const type = state.schema.nodes[FIELD_TOKEN];
      if (type === undefined) return false;
      // Takes the styles at the cursor, and leaves the cursor just after the chip.
      tr.replaceSelectionWith(type.create({ name, fallback: '' }));
      return true;
    })
    .run();
}

/** Selects the chip at `pos` and focuses the editor, as a panel closes. */
export function selectFieldToken(editor: Editor, pos: number): void {
  const node = editor.state.doc.nodeAt(pos);
  if (node?.type.name !== FIELD_TOKEN) {
    editor.commands.focus();
    return;
  }
  editor.chain().focus().setNodeSelection(pos).run();
}

/**
 * Sets the fallback of the chip at `pos`, `''` to remove it, and leaves the chip
 * selected.  Does nothing to the document when `pos` no longer holds a chip.
 */
export function setFieldFallback(editor: Editor, pos: number, fallback: string): void {
  const node = editor.state.doc.nodeAt(pos);
  if (node?.type.name !== FIELD_TOKEN) {
    editor.commands.focus();
    return;
  }
  editor
    .chain()
    .focus()
    .command(({ tr }) => {
      tr.setNodeMarkup(pos, undefined, { ...node.attrs, fallback });
      return true;
    })
    .setNodeSelection(pos)
    .run();
}

/**
 * Writes a document as HTML with each chip as its token's bare text.
 *
 * ProseMirror writes every node as an element, so a chip is first written as a
 * `<span data-field-token>` holding its token, and this takes the span away and
 * leaves the text, which is what the server reads.
 */
class TokenSerializer extends DOMSerializer {
  override serializeFragment(
    fragment: Fragment,
    options?: { document?: Document },
    target?: HTMLElement | DocumentFragment,
  ): HTMLElement | DocumentFragment {
    const written = super.serializeFragment(fragment, options, target);
    written.querySelectorAll(`span[${TOKEN_ATTRIBUTE}]`).forEach((span) => {
      span.replaceWith(...span.childNodes);
    });
    return written;
  }
}

/**
 * Makes `schema` write chips as their tokens wherever HTML is made from it: the
 * editor's `getHTML()` and a copy to the clipboard both ask `DOMSerializer.fromSchema`,
 * which answers the serializer kept in the schema's cache.
 */
function writeChipsAsTokens(schema: Schema): void {
  schema.cached.domSerializer = new TokenSerializer(
    DOMSerializer.nodesFromSchema(schema),
    DOMSerializer.marksFromSchema(schema),
  );
}

/** Draws the chip for `attrs` into `dom`. */
function drawChip(
  dom: HTMLElement,
  attrs: FieldTokenAttrs,
  labels: ReadonlyMap<string, string> | null,
): void {
  const { label, fallback, isUnknown } = chipText(attrs, labels);
  dom.className = isUnknown ? 'rich-text__field rich-text__field--unknown' : 'rich-text__field';
  if (isUnknown) dom.title = UNKNOWN_FIELD_TITLE;
  else dom.removeAttribute('title');
  if (fallback === '') {
    dom.replaceChildren(label);
    return;
  }
  const emphasis = document.createElement('em');
  emphasis.textContent = fallback;
  dom.replaceChildren(`${label}, or `, emphasis);
}

/** The node at `pos` when it is a chip, else `null`. */
function chipAt(state: EditorState, pos: number): ProseMirrorNode | null {
  const node = state.doc.nodeAt(pos);
  return node?.type.name === FIELD_TOKEN ? node : null;
}

/**
 * The `fieldToken` node: an inline atom, one unit the cursor steps over and
 * Backspace and Delete remove whole, shown as a chip and written as its token.
 */
export const FieldToken = Node.create<FieldTokenOptions>({
  name: FIELD_TOKEN,
  group: 'inline',
  inline: true,
  atom: true,
  selectable: true,
  draggable: false,
  // Ahead of the editor's own keys, so Space on a selected chip opens it rather
  // than typing over it.
  priority: 1000,

  addOptions() {
    return { catalog: new FieldCatalog(), onOpen: () => undefined };
  },

  addAttributes() {
    return {
      name: { default: '', rendered: false },
      fallback: { default: '', rendered: false },
    };
  },

  // A token is read from the HTML's text by the plugin below; this reads the element
  // a chip is written as before `TokenSerializer` unwraps it, should one ever arrive.
  parseHTML() {
    return [
      {
        tag: `span[${TOKEN_ATTRIBUTE}]`,
        getAttrs: (element) => {
          const match = WHOLE_TOKEN.exec(element.textContent);
          return match === null ? false : { name: match[1], fallback: match[2] ?? '' };
        },
      },
    ];
  },

  renderHTML({ node }) {
    const span = document.createElement('span');
    span.setAttribute(TOKEN_ATTRIBUTE, '');
    span.textContent = tokenText(fieldAttrs(node));
    return span;
  },

  renderText({ node }) {
    return tokenText(fieldAttrs(node));
  },

  addNodeView() {
    const { catalog, onOpen } = this.options;
    return ({ node, editor, getPos }) => {
      const dom = document.createElement('span');
      dom.contentEditable = 'false';
      let attrs = fieldAttrs(node);
      const draw = (): void => drawChip(dom, attrs, catalog.labels);
      draw();
      const unsubscribe = catalog.subscribe(draw);
      const handleClick = (): void => {
        const pos = getPos();
        if (!editor.isEditable || pos === undefined) return;
        editor.chain().focus().setNodeSelection(pos).run();
        onOpen(pos, attrs);
      };
      dom.addEventListener('click', handleClick);
      return {
        dom,
        update: (updated) => {
          if (updated.type !== node.type) return false;
          attrs = fieldAttrs(updated);
          draw();
          return true;
        },
        destroy: () => {
          unsubscribe();
          dom.removeEventListener('click', handleClick);
        },
      };
    };
  },

  addKeyboardShortcuts() {
    const open = (): boolean => {
      const { selection } = this.editor.state;
      if (!this.editor.isEditable) return false;
      if (!(selection instanceof NodeSelection) || selection.node.type.name !== FIELD_TOKEN) {
        return false;
      }
      this.options.onOpen(selection.from, fieldAttrs(selection.node));
      return true;
    };
    const remove = (direction: -1 | 1): boolean => {
      const { state } = this.editor;
      const { selection } = state;
      if (!selection.empty) return false;
      const pos = direction < 0 ? selection.from - 1 : selection.from;
      if (pos < 0 || chipAt(state, pos) === null) return false;
      return this.editor.commands.deleteRange({ from: pos, to: pos + 1 });
    };
    return {
      Enter: open,
      Space: open,
      Backspace: () => remove(-1),
      Delete: () => remove(1),
    };
  },

  addProseMirrorPlugins() {
    const { type } = this;
    return [
      new Plugin({
        key: PLUGIN_KEY,
        appendTransaction: (transactions, _oldState, state) => {
          const isChange = transactions.some(
            (tr) => tr.docChanged || tr.selectionSet || tr.getMeta(PLUGIN_KEY) === CONVERT_ALL,
          );
          if (!isChange) return null;
          return convertTokens(state, type, !isWholesale(transactions));
        },
      }),
    ];
  },

  onBeforeCreate() {
    writeChipsAsTokens(this.editor.schema);
  },

  onCreate() {
    // The first content is in place before any transaction runs, so it is read here.
    this.editor.view.dispatch(
      this.editor.state.tr
        .setMeta(PLUGIN_KEY, CONVERT_ALL)
        .setMeta('preventUpdate', true)
        .setMeta('addToHistory', false),
    );
  },
});
