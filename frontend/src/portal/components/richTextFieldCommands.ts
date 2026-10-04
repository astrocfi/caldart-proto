/**
 * What the editor and a chip's panel do to a recipient field's chip: put one in, set
 * its fallback, make it another field, turn it back into words, or take it out.
 * Each leaves a plain cursor after the chip's place, so the next key typed goes in
 * beside it rather than over it.
 */
import { TextSelection } from '@tiptap/pm/state';
import type { Node as ProseMirrorNode } from '@tiptap/pm/model';
import type { Transaction } from '@tiptap/pm/state';
import type { Editor } from '@tiptap/react';

import { FIELD_TOKEN, chipAt, fieldAttrs } from './richTextTokens';
import type { FieldTokenAttrs } from './richTextTokens';

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

/**
 * Focuses the editor with a plain cursor just after the chip at `pos`, as a panel
 * closes, so the next key typed goes in beside the chip rather than over it.  With
 * no chip at `pos` the editor is only focused.
 */
export function placeCursorAfterField(editor: Editor, pos: number): void {
  if (chipAt(editor.state, pos) === null) {
    editor.commands.focus();
    return;
  }
  editor
    .chain()
    .focus()
    .setTextSelection(pos + 1)
    .run();
}

/**
 * Changes the chip at `pos`, which must still be the chip `expected` the panel was
 * opened on, and leaves a plain cursor after whatever took its place.  `change`
 * edits the transaction and answers how many positions the chip's place now spans.
 * When `pos` no longer holds that very chip, the document is left alone and the
 * editor is only focused.
 */
function changeField(
  editor: Editor,
  pos: number,
  expected: FieldTokenAttrs,
  change: (tr: Transaction, node: ProseMirrorNode) => number,
): void {
  const node = chipAt(editor.state, pos);
  const attrs = node === null ? null : fieldAttrs(node);
  if (node === null || attrs?.name !== expected.name || attrs.fallback !== expected.fallback) {
    editor.commands.focus();
    return;
  }
  editor
    .chain()
    .focus()
    .command(({ tr }) => {
      const size = change(tr, node);
      tr.setSelection(TextSelection.create(tr.doc, pos + size));
      return true;
    })
    .run();
}

/** Sets the fallback of the chip at `pos`, `''` to take it off (see `changeField`). */
export function setFieldFallback(
  editor: Editor,
  pos: number,
  expected: FieldTokenAttrs,
  fallback: string,
): void {
  changeField(editor, pos, expected, (tr, node) => {
    tr.setNodeMarkup(pos, undefined, { ...node.attrs, fallback });
    return 1;
  });
}

/** Makes the chip at `pos` the field `name`, keeping its fallback (see `changeField`). */
export function renameField(
  editor: Editor,
  pos: number,
  expected: FieldTokenAttrs,
  name: string,
): void {
  changeField(editor, pos, expected, (tr, node) => {
    tr.setNodeMarkup(pos, undefined, { ...node.attrs, name });
    return 1;
  });
}

/**
 * Puts the chip at `pos` back as words: its field's name alone, `nickname` for
 * `{nickname|pal}`, which is no token, so it stays as written (see `changeField`).
 */
export function fieldToWords(editor: Editor, pos: number, expected: FieldTokenAttrs): void {
  changeField(editor, pos, expected, (tr, node) => {
    const words = fieldAttrs(node).name;
    tr.replaceWith(pos, pos + node.nodeSize, tr.doc.type.schema.text(words, node.marks));
    return words.length;
  });
}

/** Takes the chip at `pos` out (see `changeField`). */
export function removeField(editor: Editor, pos: number, expected: FieldTokenAttrs): void {
  changeField(editor, pos, expected, (tr, node) => {
    tr.delete(pos, pos + node.nodeSize);
    return 0;
  });
}
