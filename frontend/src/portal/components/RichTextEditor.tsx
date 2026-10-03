/**
 * A rich text editor: a toolbar over an editing area, reading and writing HTML.
 *
 * It is built on TipTap, which keeps the document in ProseMirror's model rather
 * than in the browser's own `contenteditable` HTML, so what it writes is always
 * the small set of tags the toolbar offers.  The server sanitizes the HTML again
 * whatever the editor wrote: the editor is a convenience, never the guard.
 *
 * The toolbar's buttons are Bold, Italic, Heading, Bulleted list, Numbered list,
 * Link, and Image, each an icon with its name beside it, followed by any extra
 * controls the caller passes.  Link and Image open a small panel under the
 * toolbar (`RichTextPanels.tsx`).
 */
import { Image } from '@tiptap/extension-image';
import { Link } from '@tiptap/extension-link';
import { EditorContent, useEditor, useEditorState } from '@tiptap/react';
import type { Editor } from '@tiptap/react';
import { StarterKit } from '@tiptap/starter-kit';
import { useEffect, useImperativeHandle, useRef, useState } from 'react';
import type { ChangeEvent, JSX, ReactNode, Ref } from 'react';

import {
  BoldIcon,
  BulletListIcon,
  HeadingIcon,
  ImageIcon,
  ItalicIcon,
  LinkIcon,
  NumberedListIcon,
} from './icons';
import type { IconProps } from './icons';
import { emailImageSize } from './richText';
import { ImagePanel, LinkPanel } from './RichTextPanels';
import type { UploadState } from './RichTextPanels';

/** The image types the picker offers; the server accepts these and no others. */
export const IMAGE_TYPES = 'image/png,image/jpeg,image/gif,image/webp';

/** The heading level the Heading button sets. */
const HEADING_LEVEL = 2;

/** What `onUploadImage` resolves to: where the image is stored and its size. */
export interface UploadedImage {
  url: string;
  width: number;
  height: number;
}

/** What a caller can do to the editor through its `ref`. */
export interface RichTextEditorHandle {
  /** Puts `text` in at the cursor, replacing any selection, and focuses the editor. */
  insertText: (text: string) => void;
  /** Moves the focus into the editing area. */
  focus: () => void;
  /** Whether `node` is the editing area or inside it. */
  contains: (node: Node | null) => boolean;
}

export interface RichTextEditorProps {
  /** The editing area's accessible name, such as "Message". */
  label: string;
  /** The message as HTML; `''` for an empty one. */
  value: string;
  /** Receives the message as HTML after every change, `''` once it is empty. */
  onChange: (html: string) => void;
  /**
   * Uploads one image the sender picked and resolves to where it is stored, or
   * rejects with an `Error` whose message says why, which the panel shows.
   */
  onUploadImage: (file: File) => Promise<UploadedImage>;
  /** More toolbar controls, after the built-in buttons. */
  toolbarExtra?: ReactNode;
  /** Ids of the hint or error that describe the editing area. */
  describedBy?: string;
  /** Marks the editing area invalid, for a message the server refused. */
  invalid?: boolean;
  /** When true the toolbar is off and the text cannot be changed. */
  readOnly?: boolean;
  ref?: Ref<RichTextEditorHandle>;
}

/** Which panel, if any, is open under the toolbar. */
type OpenPanel =
  | { kind: 'none' }
  | { kind: 'link'; href: string; isEditing: boolean }
  | { kind: 'image'; fileName: string; upload: UploadState };

/** The editing area's own attributes: its role, its name, and how it is described. */
function areaAttributes(
  label: string,
  describedBy: string | undefined,
  invalid: boolean,
): Record<string, string> {
  return {
    class: 'rich-text__area',
    role: 'textbox',
    'aria-multiline': 'true',
    'aria-label': label,
    ...(describedBy === undefined ? {} : { 'aria-describedby': describedBy }),
    ...(invalid ? { 'aria-invalid': 'true' } : {}),
  };
}

/** The editor's HTML as `onChange` reports it: `''` for an empty document. */
function htmlOf(editor: Editor): string {
  return editor.isEmpty ? '' : editor.getHTML();
}

/**
 * A toolbar and an editing area for a message written as HTML.
 *
 * `value` is read when it changes from outside, such as a draft loading; typing
 * reports through `onChange` and never resets the cursor.  The editor writes only
 * paragraphs, line breaks, bold, italic, underline, strike-through, headings,
 * lists, quotations, rules, links, and images.  A link's `target` and `rel` are
 * left off, and an inserted image carries its description and the width and height
 * it is shown at in an email (`emailImageSize`).
 */
export function RichTextEditor({
  label,
  value,
  onChange,
  onUploadImage,
  toolbarExtra,
  describedBy,
  invalid = false,
  readOnly = false,
  ref,
}: RichTextEditorProps): JSX.Element {
  const [panel, setPanel] = useState<OpenPanel>({ kind: 'none' });
  const fileInputRef = useRef<HTMLInputElement>(null);
  // The latest `onChange`, read by the editor's update handler, which TipTap binds once.
  const onChangeRef = useRef(onChange);
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        code: false,
        codeBlock: false,
        heading: { levels: [1, 2, 3] },
        link: false,
      }),
      Link.configure({
        openOnClick: false,
        autolink: true,
        defaultProtocol: 'https',
        protocols: ['mailto'],
        HTMLAttributes: { target: null, rel: null },
      }),
      Image,
    ],
    content: value,
    editable: !readOnly,
    editorProps: { attributes: areaAttributes(label, describedBy, invalid) },
    onUpdate: ({ editor: updated }) => onChangeRef.current(htmlOf(updated)),
  });

  const active = useEditorState({
    editor,
    selector: ({ editor: current }) => ({
      bold: current.isActive('bold'),
      italic: current.isActive('italic'),
      heading: current.isActive('heading', { level: HEADING_LEVEL }),
      bulletList: current.isActive('bulletList'),
      orderedList: current.isActive('orderedList'),
      link: current.isActive('link'),
    }),
  });

  useEffect(() => {
    if (htmlOf(editor) !== value) editor.commands.setContent(value, { emitUpdate: false });
  }, [editor, value]);

  useEffect(() => {
    editor.setEditable(!readOnly, false);
  }, [editor, readOnly]);

  useEffect(() => {
    editor.setOptions({ editorProps: { attributes: areaAttributes(label, describedBy, invalid) } });
  }, [editor, label, describedBy, invalid]);

  useImperativeHandle(
    ref,
    () => ({
      insertText: (text: string) => {
        editor.chain().focus().insertContent(text).run();
      },
      focus: () => {
        editor.commands.focus();
      },
      contains: (node: Node | null) => node !== null && editor.view.dom.contains(node),
    }),
    [editor],
  );

  const handlePanelClose = (): void => {
    setPanel({ kind: 'none' });
    editor.commands.focus();
  };

  const handleLinkOpen = (): void => {
    const href = editor.getAttributes('link').href as string | undefined;
    setPanel({ kind: 'link', href: href ?? '', isEditing: href !== undefined });
  };

  const handleLinkApply = (href: string): void => {
    const chain = editor.chain().focus().extendMarkRange('link');
    if (editor.state.selection.empty && !active.link) {
      // Nothing selected: the address itself becomes the link's words.
      chain
        .insertContent({
          type: 'text',
          text: href.replace(/^mailto:/, ''),
          marks: [{ type: 'link', attrs: { href } }],
        })
        .run();
    } else {
      chain.setLink({ href }).run();
    }
    setPanel({ kind: 'none' });
  };

  const handleLinkRemove = (): void => {
    editor.chain().focus().extendMarkRange('link').unsetLink().run();
    setPanel({ kind: 'none' });
  };

  const handleImagePick = (event: ChangeEvent<HTMLInputElement>): void => {
    const file = event.target.files?.[0];
    // Cleared, so picking the same file again still reports a change.
    event.target.value = '';
    if (file === undefined) return;
    setPanel({ kind: 'image', fileName: file.name, upload: { status: 'uploading' } });
    onUploadImage(file).then(
      (image) => {
        setPanel((open) =>
          open.kind === 'image' && open.fileName === file.name
            ? { ...open, upload: { status: 'ready', ...image } }
            : open,
        );
      },
      (error: unknown) => {
        const message = error instanceof Error ? error.message : 'The image could not be uploaded.';
        setPanel((open) =>
          open.kind === 'image' && open.fileName === file.name
            ? { ...open, upload: { status: 'failed', message } }
            : open,
        );
      },
    );
  };

  const handleImageInsert = (alt: string): void => {
    if (panel.kind !== 'image' || panel.upload.status !== 'ready') return;
    const { url, width, height } = panel.upload;
    editor
      .chain()
      .focus()
      .setImage({ src: url, alt, ...emailImageSize(width, height) })
      .run();
    setPanel({ kind: 'none' });
  };

  return (
    <div className="rich-text">
      <div className="rich-text__toolbar" role="group" aria-label={`${label} formatting`}>
        <ToolbarButton
          icon={BoldIcon}
          label="Bold"
          isPressed={active.bold}
          disabled={readOnly}
          onClick={() => editor.chain().focus().toggleBold().run()}
        />
        <ToolbarButton
          icon={ItalicIcon}
          label="Italic"
          isPressed={active.italic}
          disabled={readOnly}
          onClick={() => editor.chain().focus().toggleItalic().run()}
        />
        <ToolbarButton
          icon={HeadingIcon}
          label="Heading"
          isPressed={active.heading}
          disabled={readOnly}
          onClick={() => editor.chain().focus().toggleHeading({ level: HEADING_LEVEL }).run()}
        />
        <ToolbarButton
          icon={BulletListIcon}
          label="Bulleted list"
          isPressed={active.bulletList}
          disabled={readOnly}
          onClick={() => editor.chain().focus().toggleBulletList().run()}
        />
        <ToolbarButton
          icon={NumberedListIcon}
          label="Numbered list"
          isPressed={active.orderedList}
          disabled={readOnly}
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
        />
        <ToolbarButton
          icon={LinkIcon}
          label="Link"
          isPressed={active.link}
          disabled={readOnly}
          onClick={handleLinkOpen}
        />
        <ToolbarButton
          icon={ImageIcon}
          label="Image"
          disabled={readOnly}
          onClick={() => fileInputRef.current?.click()}
        />
        <input
          ref={fileInputRef}
          type="file"
          accept={IMAGE_TYPES}
          className="visually-hidden"
          tabIndex={-1}
          aria-label="Choose an image"
          onChange={handleImagePick}
        />
        {toolbarExtra}
      </div>
      {panel.kind === 'link' ? (
        <LinkPanel
          initialAddress={panel.href}
          isEditing={panel.isEditing}
          onApply={handleLinkApply}
          onRemove={handleLinkRemove}
          onCancel={handlePanelClose}
        />
      ) : null}
      {panel.kind === 'image' ? (
        <ImagePanel
          fileName={panel.fileName}
          upload={panel.upload}
          onInsert={handleImageInsert}
          onCancel={handlePanelClose}
        />
      ) : null}
      <EditorContent editor={editor} />
    </div>
  );
}

interface ToolbarButtonProps {
  icon: (props: IconProps) => JSX.Element;
  label: string;
  /** For a style the selection can be in: whether it is. */
  isPressed?: boolean;
  disabled: boolean;
  onClick: () => void;
}

/** One toolbar button: its icon and its name, pressed while its style applies. */
function ToolbarButton({
  icon: Icon,
  label,
  isPressed,
  disabled,
  onClick: handleClick,
}: ToolbarButtonProps): JSX.Element {
  return (
    <button
      type="button"
      className="rich-text__button"
      aria-pressed={isPressed}
      disabled={disabled}
      // A press keeps the focus, and with it the cursor, in the editing area, so the
      // style applies to the words typed next; the keyboard still reaches the button.
      onMouseDown={(event) => event.preventDefault()}
      onClick={handleClick}
    >
      <Icon />
      <span>{label}</span>
    </button>
  );
}
