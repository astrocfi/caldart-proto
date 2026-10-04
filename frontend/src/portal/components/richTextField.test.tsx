import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { closeHistory } from '@tiptap/pm/history';
import { NodeSelection } from '@tiptap/pm/state';
import type { Editor, TiptapEditorHTMLElement } from '@tiptap/react';
import { createRef, useState } from 'react';
import type { JSX, Ref } from 'react';
import { describe, expect, it, vi } from 'vitest';

import type { BulkEmailField } from '@/portal/api/types';
import { FIELDS } from '@test/fixtures/bulkEmail';
import { renderWithProviders } from '@test/render';

import { RichTextEditor } from './RichTextEditor';
import { fieldPhrase } from './RichTextFieldPanels';
import type { RichTextEditorHandle } from './RichTextEditor';
import { setFieldFallback } from './richTextFieldCommands';
import {
  FALLBACK_BLANK_ERROR,
  FALLBACK_ERROR,
  UNKNOWN_FIELD_FLAG,
  UNKNOWN_FIELD_TITLE,
  chipText,
} from './richTextTokens';

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

/** The fallback box of the panel a first-name chip opens. */
const FALLBACK_LABEL = "If we don't have their first name, show";

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
      `{nickname} ${UNKNOWN_FIELD_FLAG}`,
    ]);
  });

  it('copies a chip as its token', async () => {
    renderWithProviders(<Harness initial="<p>Dear {first_name|friend}</p>" />);
    await chip();

    await placeCursor(6, true);
    const copied = await userEvent.copy();

    expect([copied?.getData('text/plain'), copied?.getData('text/html')]).toEqual([
      '{first_name|friend}',
      '{first_name|friend}',
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

  it.each([
    ['two spaces in a row', '{first_name|Tom  Jo}'],
    ['a tab', '{first_name|Tom\tJo}'],
    ['a non-breaking space', '{first_name|Tom\u00a0Jo}'],
  ])('leaves a token whose fallback holds %s as text', async (_case, token) => {
    renderWithProviders(<Harness initial="<p>Dear ,</p>" />);

    await placeCursor(6);
    typeText(`${token}!`);

    expect([area().querySelector('.rich-text__field'), area().textContent]).toEqual([
      null,
      `Dear ${token}!,`,
    ]);
  });

  it('keeps undo and redo working across a token that became a chip', async () => {
    const handleChange = vi.fn();
    renderWithProviders(<Harness initial="<p>Dear ,</p>" onChange={handleChange} />);
    const seen: string[] = [];
    const step = (run: () => void): void => {
      act(run);
      seen.push(editor().getHTML());
    };

    await placeCursor(6);
    typeText('{first_name}');
    // A pause between the token and what follows it, as the history groups by time.
    act(() => {
      const { view } = editor();
      view.dispatch(closeHistory(view.state.tr));
    });
    typeText(' hi');
    step(() => editor().commands.undo());
    step(() => editor().commands.setTextSelection(1));
    step(() => editor().commands.undo());
    step(() => editor().commands.redo());
    step(() => editor().commands.setTextSelection(1));
    step(() => editor().commands.redo());
    step(() => editor().commands.undo());
    step(() => editor().commands.undo());

    expect(seen).toEqual([
      '<p>Dear {first_name},</p>',
      '<p>Dear {first_name},</p>',
      '<p>Dear ,</p>',
      '<p>Dear {first_name},</p>',
      '<p>Dear {first_name},</p>',
      '<p>Dear {first_name} hi,</p>',
      '<p>Dear {first_name},</p>',
      '<p>Dear ,</p>',
    ]);
  });

  it('leaves the chip in place when undo takes back what followed it', async () => {
    renderWithProviders(<Harness initial="<p>Dear ,</p>" />);

    await placeCursor(6);
    typeText('{first_name}');
    act(() => {
      const { view } = editor();
      view.dispatch(closeHistory(view.state.tr));
    });
    typeText(' hi');
    act(() => {
      editor().commands.undo();
    });

    expect((await chip()).textContent).toBe('First name');
  });

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
    await userEvent.type(screen.getByLabelText(FALLBACK_LABEL), 'friend');
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

    expect(screen.getByLabelText(FALLBACK_LABEL)).toHaveValue('friend');
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

  it('leaves the chip as it was on Cancel, with the cursor just after it', async () => {
    const handleChange = vi.fn();
    renderWithProviders(
      <Harness initial="<p>Dear {first_name|friend}</p>" onChange={handleChange} />,
    );

    await userEvent.click(await chip());
    await userEvent.clear(screen.getByLabelText(FALLBACK_LABEL));
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    await waitFor(() => expect(area()).toHaveFocus());

    expect([
      handleChange.mock.calls.length,
      editor().state.selection.from,
      editor().state.selection.to,
    ]).toEqual([0, 7, 7]);
  });

  it.each(['a{b', 'a|b', 'a<b', 'a>b', 'a}b'])(
    'refuses a fallback holding %s, and changes nothing',
    async (fallback) => {
      const handleChange = vi.fn();
      renderWithProviders(<Harness initial="<p>{first_name}</p>" onChange={handleChange} />);

      await userEvent.click(await chip());
      // Typed into the box, where user-event reads `{` as the start of a key name.
      await userEvent.type(screen.getByLabelText(FALLBACK_LABEL), fallback.replace('{', '{{'));
      await userEvent.click(screen.getByRole('button', { name: 'Apply' }));

      expect([screen.getByRole('alert').textContent, handleChange.mock.calls.length]).toEqual([
        FALLBACK_ERROR,
        0,
      ]);
    },
  );

  it.each([
    ['runs of spaces', 'Tom   Jo', '{first_name|Tom Jo}'],
    ['spaces at either end', '  friend ', '{first_name|friend}'],
    ['a non-breaking space', 'Tom\u00a0Jo', '{first_name|Tom Jo}'],
  ])('puts %s in a fallback as single spaces', async (_case, typed, token) => {
    const handleChange = vi.fn();
    renderWithProviders(<Harness initial="<p>{first_name}</p>" onChange={handleChange} />);

    await userEvent.click(await chip());
    const box = screen.getByLabelText(FALLBACK_LABEL);
    await userEvent.click(box);
    await userEvent.paste(typed);
    await userEvent.click(screen.getByRole('button', { name: 'Apply' }));

    expect(lastChange(handleChange)).toBe(`<p>${token}</p>`);
  });

  it('refuses a fallback of only spaces, and changes nothing', async () => {
    const handleChange = vi.fn();
    renderWithProviders(<Harness initial="<p>{first_name}</p>" onChange={handleChange} />);

    await userEvent.click(await chip());
    await userEvent.type(screen.getByLabelText(FALLBACK_LABEL), '   ');
    await userEvent.click(screen.getByRole('button', { name: 'Apply' }));

    expect([screen.getByRole('alert').textContent, handleChange.mock.calls.length]).toEqual([
      FALLBACK_BLANK_ERROR,
      0,
    ]);
  });

  it('closes the panel when its chip is taken out while it is open', async () => {
    const handleChange = vi.fn();
    renderWithProviders(
      <Harness initial="<p>{first_name} {dart_name}</p>" onChange={handleChange} />,
    );
    const [first] = await chips();
    if (first === undefined) throw new Error('No chip.');

    await userEvent.click(first);
    act(() => {
      editor().commands.deleteRange({ from: 1, to: 3 });
    });

    expect([
      screen.queryByRole('region', { name: 'First name field' }),
      lastChange(handleChange),
    ]).toEqual([null, '<p>{dart_name}</p>']);
  });

  it('leaves the message alone when the chip the panel opened on is no longer there', async () => {
    renderWithProviders(<Harness initial="<p>{first_name} {dart_name}</p>" />);
    await chips();

    act(() => setFieldFallback(editor(), 3, { name: 'first_name', fallback: '' }, 'friend'));

    expect(editor().getHTML()).toBe('<p>{first_name} {dart_name}</p>');
  });

  it('follows its chip when the message changes before it', async () => {
    const handleChange = vi.fn();
    renderWithProviders(
      <Harness initial="<p>{first_name} {dart_name}</p>" onChange={handleChange} />,
    );
    const [, second] = await chips();
    if (second === undefined) throw new Error('No second chip.');

    await userEvent.click(second);
    act(() => {
      editor().commands.insertContentAt(1, 'Hi ');
    });
    await userEvent.type(screen.getByLabelText("If we don't have their DART, show"), 'yours');
    await userEvent.click(screen.getByRole('button', { name: 'Apply' }));

    expect(lastChange(handleChange)).toBe('<p>Hi {first_name} {dart_name|yours}</p>');
  });

  it('follows its chip when opening the panel turns a typed token beside it into a chip', async () => {
    const handleChange = vi.fn();
    renderWithProviders(<Harness initial="<p>Dear ,</p>" onChange={handleChange} />);

    await placeCursor(6);
    typeText('{dart_name}');
    // A chip put in just after the typed token and selected, so the token stays text.
    act(() => {
      const { view } = editor();
      const type = view.state.schema.nodes.fieldToken;
      if (type === undefined) throw new Error('No fieldToken node.');
      const tr = view.state.tr.insert(17, type.create({ name: 'first_name', fallback: '' }));
      view.dispatch(tr.setSelection(NodeSelection.create(tr.doc, 17)));
    });
    await userEvent.keyboard('{Enter}');
    await userEvent.type(screen.getByLabelText(FALLBACK_LABEL), 'friend');
    await userEvent.click(screen.getByRole('button', { name: 'Apply' }));

    expect(lastChange(handleChange)).toBe('<p>Dear {dart_name}{first_name|friend},</p>');
  });

  it('titles the panel with the field it is for', async () => {
    renderWithProviders(<Harness initial="<p>{first_name}</p>" />);

    await userEvent.click(await chip());

    expect(screen.getByRole('region', { name: 'First name field' }).firstChild).toHaveTextContent(
      'First name',
    );
  });

  it('puts the next key typed after the chip once Apply closes the panel', async () => {
    const handleChange = vi.fn();
    renderWithProviders(<Harness initial="<p>Dear {first_name},</p>" onChange={handleChange} />);

    await userEvent.click(await chip());
    await userEvent.type(screen.getByLabelText(FALLBACK_LABEL), 'friend');
    await userEvent.click(screen.getByRole('button', { name: 'Apply' }));
    typeText('X');

    expect(lastChange(handleChange)).toBe('<p>Dear {first_name|friend}X,</p>');
  });

  it('leaves a plain cursor after the chip when Escape closes the panel', async () => {
    renderWithProviders(<Harness initial="<p>Dear {first_name},</p>" />);

    await userEvent.click(await chip());
    await userEvent.keyboard('{Escape}');

    expect([
      screen.queryByRole('region', { name: 'First name field' }),
      editor().state.selection.empty,
      editor().state.selection.from,
    ]).toEqual([null, true, 7]);
  });

  it('opens no panel on a chip in a message that cannot change', async () => {
    renderWithProviders(<Harness initial="<p>{first_name}</p>" readOnly />);

    await userEvent.click(await chip());

    expect(screen.queryByRole('region', { name: 'First name field' })).toBeNull();
  });
});

describe('RichTextEditor unknown field panel', () => {
  /** Opens the panel of the one unknown chip in `<p>Hi {nickname}</p>`. */
  async function openUnknown(handleChange: (html: string) => void): Promise<void> {
    renderWithProviders(<Harness initial="<p>Hi {nickname}</p>" onChange={handleChange} />);
    await userEvent.click(await chip());
  }

  it('says the chip is not one of the fields', async () => {
    await openUnknown(vi.fn());

    expect(screen.getByRole('region', { name: 'Unknown field' })).toHaveTextContent(
      '{nickname} is not one of the fields.',
    );
  });

  it('makes the chip a field chosen from the list', async () => {
    const handleChange = vi.fn();
    await openUnknown(handleChange);

    await userEvent.click(screen.getByRole('button', { name: 'Choose a field' }));
    await userEvent.click(screen.getByRole('button', { name: 'DART' }));

    expect([lastChange(handleChange), (await chip()).textContent]).toEqual([
      '<p>Hi {dart_name}</p>',
      'DART',
    ]);
  });

  it('turns the chip into its name as words', async () => {
    const handleChange = vi.fn();
    await openUnknown(handleChange);

    await userEvent.click(screen.getByRole('button', { name: 'Turn into words' }));
    act(() => {
      editor().commands.setTextSelection(1);
    });

    expect([lastChange(handleChange), area().querySelector('.rich-text__field')]).toEqual([
      '<p>Hi nickname</p>',
      null,
    ]);
  });

  it('turns a chip with a fallback into its name alone', async () => {
    const handleChange = vi.fn();
    renderWithProviders(<Harness initial="<p>Hi {nickname|pal}</p>" onChange={handleChange} />);

    await userEvent.click(await chip());
    await userEvent.click(screen.getByRole('button', { name: 'Turn into words' }));

    expect(lastChange(handleChange)).toBe('<p>Hi nickname</p>');
  });

  it('removes the chip', async () => {
    const handleChange = vi.fn();
    await openUnknown(handleChange);

    await userEvent.click(screen.getByRole('button', { name: 'Remove' }));

    expect(lastChange(handleChange)).toBe('<p>Hi </p>');
  });
});

describe('RichTextEditor chip states', () => {
  it('keeps a selected chip marked selected when it is drawn again', async () => {
    const { rerender } = renderWithProviders(
      <Harness initial="<p>Dear {first_name}</p>" fields="loading" />,
    );
    await chip();

    await placeCursor(6, true);
    rerender(<Harness initial="<p>Dear {first_name}</p>" fields={FIELDS} />);
    const selected = await chip();

    expect([selected.textContent, selected.classList.contains('ProseMirror-selectednode')]).toEqual(
      ['First name', true],
    );
  });

  it('turns a typed token into a chip when the editor loses the focus', async () => {
    renderWithProviders(<Harness initial="<p>Dear ,</p>" />);

    await placeCursor(6);
    typeText('{first_name}');
    act(() => {
      editor().view.dom.blur();
    });

    expect((await chip()).textContent).toBe('First name');
  });
});

describe('fieldPhrase', () => {
  it.each([
    ['First name', 'first name'],
    ['Email address', 'email address'],
    ['DART', 'DART'],
  ])('names %s in a sentence as %s', (label, phrase) => {
    expect(fieldPhrase(label)).toBe(phrase);
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
