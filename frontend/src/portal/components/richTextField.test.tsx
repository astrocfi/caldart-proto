import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { Editor, TiptapEditorHTMLElement } from '@tiptap/react';
import { createRef, useState } from 'react';
import type { JSX, Ref } from 'react';
import { describe, expect, it, vi } from 'vitest';

import type { BulkEmailField } from '@/portal/api/types';
import { FIELDS } from '@test/fixtures/bulkEmail';
import { renderWithProviders } from '@test/render';

import { RichTextEditor } from './RichTextEditor';
import type { RichTextEditorHandle } from './RichTextEditor';
import { FALLBACK_ERROR, UNKNOWN_FIELD_TITLE, chipText } from './richTextField';

interface HarnessProps {
  initial?: string;
  /** The catalog, or `'loading'` for one not yet answered. */
  fields?: BulkEmailField[] | 'loading';
  onChange?: (html: string) => void;
  readOnly?: boolean;
  editorRef?: Ref<RichTextEditorHandle>;
}

/** The editor holding its own value, with the field catalog, reporting each change. */
function Harness({
  initial = '',
  fields = FIELDS,
  onChange: handleChange = () => undefined,
  readOnly = false,
  editorRef,
}: HarnessProps): JSX.Element {
  const [value, setValue] = useState(initial);
  return (
    <RichTextEditor
      ref={editorRef}
      label="Message"
      value={value}
      fields={fields === 'loading' ? undefined : fields}
      readOnly={readOnly}
      onChange={(html) => {
        setValue(html);
        handleChange(html);
      }}
      onUploadImage={() => Promise.reject(new Error('unused'))}
    />
  );
}

function area(): HTMLElement {
  return screen.getByRole('textbox', { name: 'Message' });
}

/** The TipTap editor behind the editing area, to place the cursor and read its HTML. */
function editor(): Editor {
  const { editor: instance } = area() as TiptapEditorHTMLElement;
  if (instance === undefined) throw new Error('The editing area has no editor.');
  return instance;
}

/** The chips in the editing area, once there is at least one. */
async function chips(): Promise<HTMLElement[]> {
  await waitFor(() => expect(area().querySelector('.rich-text__field')).not.toBeNull());
  return [...area().querySelectorAll<HTMLElement>('.rich-text__field')];
}

/** The one chip in the editing area. */
async function chip(): Promise<HTMLElement> {
  const [first] = await chips();
  if (first === undefined) throw new Error('No chip.');
  return first;
}

/**
 * Focuses the editing area and puts the cursor at `pos`, or selects the chip at `pos`
 * with `isNode`.
 */
async function placeCursor(pos: number, isNode = false): Promise<void> {
  await userEvent.click(area());
  act(() => {
    if (isNode) editor().commands.setNodeSelection(pos);
    else editor().commands.setTextSelection(pos);
  });
}

/**
 * Types `text` at the cursor a character at a time, each its own transaction, as
 * ProseMirror reads keystrokes.  jsdom has no text input of its own to read.
 */
function typeText(text: string): void {
  for (const character of text) {
    act(() => {
      const { view } = editor();
      view.dispatch(view.state.tr.insertText(character));
    });
  }
}

/** Lets the editor finish being created, when it reads its first content. */
async function settle(): Promise<void> {
  await act(() => new Promise((resolve) => setTimeout(resolve, 0)));
}

/** The latest HTML the editor reported. */
function lastChange(handleChange: ReturnType<typeof vi.fn>): string {
  return handleChange.mock.lastCall?.[0] as string;
}

describe('RichTextEditor field chips', () => {
  it('puts a field in as a chip showing its label', async () => {
    const editorRef = createRef<RichTextEditorHandle>();
    renderWithProviders(<Harness initial="<p>Dear ,</p>" editorRef={editorRef} />);

    await placeCursor(6);
    act(() => editorRef.current?.insertField('first_name'));

    expect((await chip()).textContent).toBe('First name');
  });

  it('writes an inserted field as its token, with the cursor after it', async () => {
    const handleChange = vi.fn();
    const editorRef = createRef<RichTextEditorHandle>();
    renderWithProviders(
      <Harness initial="<p>Dear ,</p>" onChange={handleChange} editorRef={editorRef} />,
    );

    await placeCursor(6);
    act(() => editorRef.current?.insertField('first_name'));
    act(() => {
      editor().commands.insertContent('!');
    });

    expect(lastChange(handleChange)).toBe('<p>Dear {first_name}!,</p>');
  });

  it('removes the chip before the cursor whole on Backspace, and nothing else', async () => {
    const handleChange = vi.fn();
    renderWithProviders(
      <Harness initial="<p>Dear {first_name} pilots</p>" onChange={handleChange} />,
    );
    await chip();

    await placeCursor(7);
    await userEvent.keyboard('{Backspace}');

    expect(lastChange(handleChange)).toBe('<p>Dear  pilots</p>');
  });

  it('removes the chip after the cursor whole on Delete', async () => {
    const handleChange = vi.fn();
    renderWithProviders(
      <Harness initial="<p>Dear {first_name} pilots</p>" onChange={handleChange} />,
    );
    await chip();

    await placeCursor(6);
    await userEvent.keyboard('{Delete}');

    expect(lastChange(handleChange)).toBe('<p>Dear  pilots</p>');
  });

  it('shows a fallback beside the label', async () => {
    renderWithProviders(<Harness initial="<p>Dear {first_name|friend},</p>" />);

    expect((await chip()).textContent).toBe('First name, or friend');
  });

  it('shows the name made readable while the fields load, then the label', async () => {
    const { rerender } = renderWithProviders(
      <Harness initial="<p>{first_name}</p>" fields="loading" />,
    );
    const shown = [(await chip()).textContent];

    rerender(<Harness initial="<p>{first_name}</p>" fields={FIELDS} />);
    shown.push((await chip()).textContent);

    expect(shown).toEqual(['first name', 'First name']);
  });

  it('marks a name that is not one of the fields as unknown, showing its token', async () => {
    renderWithProviders(<Harness initial="<p>Hi {nickname}</p>" />);

    const unknown = await chip();

    expect([unknown.className, unknown.title, unknown.textContent]).toEqual([
      'rich-text__field rich-text__field--unknown',
      UNKNOWN_FIELD_TITLE,
      '{nickname}',
    ]);
  });

  it('copies a chip as its token', async () => {
    renderWithProviders(<Harness initial="<p>Dear {first_name|friend}</p>" />);
    await chip();

    await placeCursor(6, true);
    const copied = await userEvent.copy();

    expect([copied?.getData('text/plain'), copied?.getData('text/html')]).toEqual([
      '{first_name|friend}',
      expect.stringContaining('{first_name|friend}'),
    ]);
  });

  it('turns pasted token text into a chip', async () => {
    const handleChange = vi.fn();
    renderWithProviders(<Harness initial="<p>Dear ,</p>" onChange={handleChange} />);

    await placeCursor(6);
    await userEvent.paste('{dart_name}');

    expect([(await chip()).textContent, lastChange(handleChange)]).toEqual([
      'DART',
      '<p>Dear {dart_name},</p>',
    ]);
  });
});

describe('RichTextEditor typed tokens', () => {
  it('leaves a token being typed as text while the cursor is beside it', async () => {
    renderWithProviders(<Harness initial="<p>Dear ,</p>" />);

    await placeCursor(6);
    typeText('{first_name}');

    expect([area().querySelector('.rich-text__field'), area().textContent]).toEqual([
      null,
      'Dear {first_name},',
    ]);
  });

  it('turns a typed token into a chip once the cursor leaves it', async () => {
    const handleChange = vi.fn();
    renderWithProviders(<Harness initial="<p>Dear ,</p>" onChange={handleChange} />);

    await placeCursor(6);
    typeText('{first_name}!');

    expect([(await chip()).textContent, lastChange(handleChange)]).toEqual([
      'First name',
      '<p>Dear {first_name}!,</p>',
    ]);
  });

  it('leaves a doubled brace as text', async () => {
    const handleChange = vi.fn();
    renderWithProviders(<Harness initial="<p>Dear ,</p>" onChange={handleChange} />);

    await placeCursor(6);
    typeText('{{first_name}} ');

    expect([area().querySelector('.rich-text__field'), lastChange(handleChange)]).toEqual([
      null,
      '<p>Dear {{first_name}} ,</p>',
    ]);
  });

  it.each([
    ['a brace before it', 6, '{', '<p>Dear {{first_name},</p>'],
    ['a brace after it', 7, '}', '<p>Dear {first_name}},</p>'],
  ])(
    'turns a chip back into text when %s doubles one of its own',
    async (_where, pos, brace, html) => {
      const handleChange = vi.fn();
      renderWithProviders(<Harness initial="<p>Dear {first_name},</p>" onChange={handleChange} />);
      await chip();

      await placeCursor(pos);
      typeText(brace);

      expect([area().querySelector('.rich-text__field'), lastChange(handleChange)]).toEqual([
        null,
        html,
      ]);
    },
  );

  it('leaves a token split by formatting as text', async () => {
    renderWithProviders(<Harness initial="<p><strong>{first</strong>_name}</p>" />);
    await settle();

    expect([area().querySelector('.rich-text__field'), editor().getHTML()]).toEqual([
      null,
      '<p><strong>{first</strong>_name}</p>',
    ]);
  });
});

describe('RichTextEditor field round trip', () => {
  it.each([
    ['at the start of a paragraph', '<p>{first_name}, hello</p>', 1],
    ['at the end of a paragraph', '<p>Dear {first_name}</p>', 1],
    ['side by side', '<p>{first_name}{dart_name}</p>', 2],
    ['with a fallback holding an ampersand', '<p>{first_name|Tom &amp; Jo}</p>', 1],
    ['inside a link', '<p><a href="https://caldart.org">Hi {first_name} there</a></p>', 1],
    ['inside a heading', '<h2>News for {first_name}</h2><p></p>', 1],
    ['inside a list item', '<ul><li><p>{dart_name}</p></li></ul><p></p>', 1],
    ['inside bold', '<p><strong>Dear {first_name}</strong></p>', 1],
    ['inside italic', '<p><em>{first_name|friend}</em></p>', 1],
    ['beside a token in a link address', '<p><a href="https://x.org/{email}">{email}</a></p>', 1],
  ])('keeps the HTML of a chip %s', async (_where, html, count) => {
    renderWithProviders(<Harness initial={html} />);

    const shown = await chips();

    expect([shown.length, editor().getHTML()]).toEqual([count, html]);
  });
});

describe('RichTextEditor field panel', () => {
  it('sets a fallback from the panel a click on the chip opens', async () => {
    const handleChange = vi.fn();
    renderWithProviders(<Harness initial="<p>Dear {first_name},</p>" onChange={handleChange} />);

    await userEvent.click(await chip());
    await userEvent.type(screen.getByLabelText(/If the person has no value, show/), 'friend');
    await userEvent.click(screen.getByRole('button', { name: 'Apply' }));

    expect([(await chip()).textContent, lastChange(handleChange)]).toEqual([
      'First name, or friend',
      '<p>Dear {first_name|friend},</p>',
    ]);
  });

  it('opens the panel on Enter with the chip selected', async () => {
    renderWithProviders(<Harness initial="<p>Dear {first_name}</p>" />);
    await chip();

    await placeCursor(6, true);
    await userEvent.keyboard('{Enter}');

    expect(screen.getByRole('region', { name: 'First name field' })).toBeInTheDocument();
  });

  it('opens the panel on Space with the chip selected, keeping the chip', async () => {
    renderWithProviders(<Harness initial="<p>Dear {first_name}</p>" />);
    await chip();

    await placeCursor(6, true);
    await userEvent.keyboard(' ');

    expect([screen.getByRole('region', { name: 'First name field' }), editor().getHTML()]).toEqual([
      expect.anything(),
      '<p>Dear {first_name}</p>',
    ]);
  });

  it('starts the box from the fallback already set', async () => {
    renderWithProviders(<Harness initial="<p>{first_name|friend}</p>" />);

    await userEvent.click(await chip());

    expect(screen.getByLabelText(/If the person has no value, show/)).toHaveValue('friend');
  });

  it('takes the fallback off with Clear', async () => {
    const handleChange = vi.fn();
    renderWithProviders(
      <Harness initial="<p>Dear {first_name|friend},</p>" onChange={handleChange} />,
    );

    await userEvent.click(await chip());
    await userEvent.click(screen.getByRole('button', { name: 'Clear' }));

    expect(lastChange(handleChange)).toBe('<p>Dear {first_name},</p>');
  });

  it('offers Clear only once a fallback is set', async () => {
    renderWithProviders(<Harness initial="<p>{first_name}</p>" />);

    await userEvent.click(await chip());

    expect(screen.queryByRole('button', { name: 'Clear' })).toBeNull();
  });

  it('leaves the chip as it was on Cancel, selected in the editor', async () => {
    const handleChange = vi.fn();
    renderWithProviders(
      <Harness initial="<p>Dear {first_name|friend}</p>" onChange={handleChange} />,
    );

    await userEvent.click(await chip());
    await userEvent.clear(screen.getByLabelText(/If the person has no value, show/));
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    await waitFor(() => expect(area()).toHaveFocus());

    expect([
      handleChange.mock.calls.length,
      editor().state.selection.from,
      editor().state.selection.to,
    ]).toEqual([0, 6, 7]);
  });

  it.each(['a{b', 'a|b', 'a<b', 'a>b', 'a}b'])(
    'refuses a fallback holding %s, and changes nothing',
    async (fallback) => {
      const handleChange = vi.fn();
      renderWithProviders(<Harness initial="<p>{first_name}</p>" onChange={handleChange} />);

      await userEvent.click(await chip());
      // Typed into the box, where user-event reads `{` as the start of a key name.
      await userEvent.type(
        screen.getByLabelText(/If the person has no value, show/),
        fallback.replace('{', '{{'),
      );
      await userEvent.click(screen.getByRole('button', { name: 'Apply' }));

      expect([screen.getByRole('alert').textContent, handleChange.mock.calls.length]).toEqual([
        FALLBACK_ERROR,
        0,
      ]);
    },
  );

  it('opens no panel on a chip in a message that cannot change', async () => {
    renderWithProviders(<Harness initial="<p>{first_name}</p>" readOnly />);

    await userEvent.click(await chip());

    expect(screen.queryByRole('region', { name: 'First name field' })).toBeNull();
  });
});

describe('chipText', () => {
  const labels = new Map([['first_name', 'First name']]);

  it.each([
    ['a known field', { name: 'first_name', fallback: '' }, labels, 'First name', false],
    ['an unknown field', { name: 'nickname', fallback: 'x' }, labels, '{nickname|x}', true],
    ['a field while loading', { name: 'home_airport', fallback: '' }, null, 'home airport', false],
  ])('reads %s', (_case, attrs, catalog, label, isUnknown) => {
    expect(chipText(attrs, catalog)).toEqual(expect.objectContaining({ label, isUnknown }));
  });
});
