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
import { DOMSerializer } from '@tiptap/pm/model';
import type { Fragment, Mark, Node as ProseMirrorNode, NodeType, Schema } from '@tiptap/pm/model';
import { isHistoryTransaction } from '@tiptap/pm/history';
import { NodeSelection, Plugin, PluginKey } from '@tiptap/pm/state';
import type { EditorState, Transaction } from '@tiptap/pm/state';
import { Node } from '@tiptap/react';

import {
  FIELD_TOKEN,
  FieldCatalog,
  TOKEN_PATTERN,
  UNKNOWN_FIELD_FLAG,
  UNKNOWN_FIELD_TITLE,
  WHOLE_TOKEN,
  chipAt,
  chipText,
  fieldAttrs,
  isFallbackEven,
  tokenText,
} from './richTextTokens';
import type { FieldTokenAttrs } from './richTextTokens';

/** The class ProseMirror marks a selected node with, kept across a redraw. */
const SELECTED_CLASS = 'ProseMirror-selectednode';

/** Marks the element a chip is first written as, before `TokenSerializer` unwraps it. */
const TOKEN_ATTRIBUTE = 'data-field-token';

/** Stands in for an image or a line break when a paragraph is read as text. */
const OBJECT_CHARACTER = '\uFFFC';

/** Marks a transaction whose token text should all become chips, cursor or not. */
const CONVERT_ALL = 'convertAll';

/** What the browser marks a paste or a drop with, which converts at once too. */
const WHOLESALE_EVENTS = new Set(['paste', 'drop']);

const PLUGIN_KEY = new PluginKey('fieldToken');

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

/**
 * Reads every paragraph of `doc` as the server would read its HTML, each chip as its
 * token's text and an image or a line break as one object character, and answers
 * which token text should become a chip and which chip should become text.
 *
 * A token written as text becomes a chip only when all of it lies in one run of text
 * with the same styles: one split by bold or a link is left as text, which the server
 * refuses, and so is one whose fallback holds whitespace other than single plain
 * spaces.  A chip becomes text again when a brace written beside it doubles one of
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
      // The server refuses a token whose fallback its plain text reads differently.
      if (!isFallbackEven(match[2] ?? '')) continue;
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
 * paste or a drop, or leave the editor, so every token in it becomes a chip whether
 * or not the cursor is beside it.
 */
function isWholesale(transactions: readonly Transaction[]): boolean {
  return transactions.some(
    (tr) =>
      tr.getMeta(PLUGIN_KEY) === CONVERT_ALL ||
      // Leaving the editor leaves whatever was being typed finished.
      tr.getMeta('blur') !== undefined ||
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
  // Toggled rather than set, so a redraw keeps ProseMirror's selected class.
  dom.classList.add('rich-text__field');
  dom.classList.toggle('rich-text__field--unknown', isUnknown);
  if (isUnknown) {
    dom.title = UNKNOWN_FIELD_TITLE;
    const flag = document.createElement('span');
    flag.className = 'rich-text__field-flag';
    flag.textContent = UNKNOWN_FIELD_FLAG;
    dom.replaceChildren(`${label} `, flag);
    return;
  }
  dom.removeAttribute('title');
  if (fallback === '') {
    dom.replaceChildren(label);
    return;
  }
  const emphasis = document.createElement('em');
  emphasis.textContent = fallback;
  dom.replaceChildren(`${label}, or `, emphasis);
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
        // Read back, since selecting the chip may have turned typed text before it
        // into a chip and moved it.
        const { selection } = editor.state;
        if (selection instanceof NodeSelection && selection.node.type.name === FIELD_TOKEN) {
          onOpen(selection.from, fieldAttrs(selection.node));
        }
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
        selectNode: () => dom.classList.add(SELECTED_CLASS),
        deselectNode: () => dom.classList.remove(SELECTED_CLASS),
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
          // Undo and redo put back exactly what was there; a token they restore as
          // text becomes a chip at the next change instead.
          if (transactions.some(isHistoryTransaction)) return null;
          const isChange = transactions.some(
            (tr) =>
              tr.docChanged ||
              tr.selectionSet ||
              tr.getMeta(PLUGIN_KEY) === CONVERT_ALL ||
              tr.getMeta('blur') !== undefined,
          );
          if (!isChange) return null;
          // Kept out of the history: undo takes back what the sender did, and the
          // history maps its steps through this one, so undoing the typing of a
          // token removes the chip it became.
          return (
            convertTokens(state, type, !isWholesale(transactions))?.setMeta(
              'addToHistory',
              false,
            ) ?? null
          );
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
