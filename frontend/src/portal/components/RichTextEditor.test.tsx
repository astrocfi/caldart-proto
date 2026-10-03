import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createRef, useState } from 'react';
import type { JSX } from 'react';
import { beforeAll, describe, expect, it, vi } from 'vitest';

import { RichTextEditor } from './RichTextEditor';
import type { RichTextEditorHandle, UploadedImage } from './RichTextEditor';
import { IMAGE_ALT_ERROR, LINK_ADDRESS_ERROR } from './RichTextPanels';

const STORED: UploadedImage = {
  url: 'https://caldart.example.org/media/bulk-email/abc.png',
  width: 1200,
  height: 600,
};

// jsdom lays nothing out, and ProseMirror measures the selection to scroll it into
// view whenever a command focuses the editor.
beforeAll(() => {
  const empty = (): DOMRectList => [] as unknown as DOMRectList;
  const rect = (): DOMRect => new DOMRect(0, 0, 0, 0);
  Range.prototype.getClientRects = empty;
  Range.prototype.getBoundingClientRect = rect;
  document.elementFromPoint = () => null;
});

interface HarnessProps {
  initial?: string;
  onChange?: (html: string) => void;
  onUploadImage?: (file: File) => Promise<UploadedImage>;
  readOnly?: boolean;
  editorRef?: React.Ref<RichTextEditorHandle>;
}

/** The editor holding its own value, reporting each change to `onChange`. */
function Harness({
  initial = '',
  onChange: handleChange = () => undefined,
  onUploadImage: handleUploadImage = () => Promise.resolve(STORED),
  readOnly = false,
  editorRef,
}: HarnessProps): JSX.Element {
  const [value, setValue] = useState(initial);
  return (
    <RichTextEditor
      ref={editorRef}
      label="Message"
      value={value}
      onChange={(html) => {
        setValue(html);
        handleChange(html);
      }}
      onUploadImage={handleUploadImage}
      readOnly={readOnly}
      toolbarExtra={<button type="button">Extra</button>}
    />
  );
}

function area(): HTMLElement {
  return screen.getByRole('textbox', { name: 'Message' });
}

/** The latest HTML the editor reported. */
function lastChange(handleChange: ReturnType<typeof vi.fn>): string {
  return handleChange.mock.lastCall?.[0] as string;
}

/** Focuses the editing area and selects everything in it. */
async function selectAll(): Promise<void> {
  await userEvent.click(area());
  await userEvent.keyboard('{Control>}a{/Control}');
}

describe('RichTextEditor', () => {
  it('names every toolbar button and the editing area', () => {
    render(<Harness />);

    const names = [
      'Bold',
      'Italic',
      'Heading',
      'Bulleted list',
      'Numbered list',
      'Link',
      'Image',
    ].map((name) => screen.getByRole('button', { name }).textContent);
    expect(names).toEqual([
      'Bold',
      'Italic',
      'Heading',
      'Bulleted list',
      'Numbered list',
      'Link',
      'Image',
    ]);
  });

  it('shows the extra toolbar controls it is given', () => {
    render(<Harness />);

    expect(screen.getByRole('button', { name: 'Extra' })).toBeInTheDocument();
  });

  it('shows the message it is given', () => {
    render(<Harness initial="<p>Hello <strong>pilots</strong></p>" />);

    expect(area().innerHTML).toContain('<p>Hello <strong>pilots</strong></p>');
  });

  it.each([
    ['Bold', '<p><strong>Hello</strong></p>'],
    ['Italic', '<p><em>Hello</em></p>'],
    // A block that ends the message is followed by an empty paragraph, so the
    // sender can always click below it and carry on writing.
    ['Heading', '<h2>Hello</h2><p></p>'],
    ['Bulleted list', '<ul><li><p>Hello</p></li></ul><p></p>'],
    ['Numbered list', '<ol><li><p>Hello</p></li></ol><p></p>'],
  ])('applies %s to the selection', async (button, expected) => {
    const handleChange = vi.fn();
    render(<Harness initial="<p>Hello</p>" onChange={handleChange} />);

    await selectAll();
    await userEvent.click(screen.getByRole('button', { name: button }));

    expect(lastChange(handleChange)).toBe(expected);
  });

  it('marks a button pressed while its style applies at the cursor', () => {
    render(<Harness initial="<p><strong>Hello</strong></p>" />);

    expect(screen.getByRole('button', { name: 'Bold' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('leaves a button unpressed while its style does not apply', () => {
    render(<Harness initial="<p>Hello</p>" />);

    expect(screen.getByRole('button', { name: 'Italic' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('reports an empty message as an empty string', async () => {
    const handleChange = vi.fn();
    render(<Harness initial="<p>Hello</p>" onChange={handleChange} />);

    await selectAll();
    await userEvent.keyboard('{Backspace}');

    expect(lastChange(handleChange)).toBe('');
  });

  it('takes a value changed from outside without reporting a change', () => {
    const handleChange = vi.fn();
    const { rerender } = render(
      <RichTextEditor
        label="Message"
        value="<p>One</p>"
        onChange={handleChange}
        onUploadImage={() => Promise.resolve(STORED)}
      />,
    );

    rerender(
      <RichTextEditor
        label="Message"
        value="<p>Two</p>"
        onChange={handleChange}
        onUploadImage={() => Promise.resolve(STORED)}
      />,
    );

    expect([area().textContent, handleChange.mock.calls.length]).toEqual(['Two', 0]);
  });

  it('turns the toolbar off and the text read-only when read-only', () => {
    render(<Harness initial="<p>Hello</p>" readOnly />);

    expect([
      screen.getByRole('button', { name: 'Bold' }),
      area().getAttribute('contenteditable'),
    ]).toEqual([expect.objectContaining({ disabled: true }), 'false']);
  });

  it('puts text in at the cursor through its handle', async () => {
    const handleChange = vi.fn();
    const editorRef = createRef<RichTextEditorHandle>();
    render(<Harness initial="<p>Hello</p>" onChange={handleChange} editorRef={editorRef} />);

    await selectAll();
    act(() => editorRef.current?.insertText('{first_name}'));

    expect(lastChange(handleChange)).toBe('<p>{first_name}</p>');
  });

  it('tells through its handle whether a node is inside the editing area', () => {
    const editorRef = createRef<RichTextEditorHandle>();
    render(<Harness initial="<p>Hello</p>" editorRef={editorRef} />);

    expect([
      editorRef.current?.contains(area()),
      editorRef.current?.contains(screen.getByRole('button', { name: 'Bold' })),
    ]).toEqual([true, false]);
  });
});

describe('RichTextEditor links', () => {
  it('asks for the address and links the selection to it', async () => {
    const handleChange = vi.fn();
    render(<Harness initial="<p>Hello</p>" onChange={handleChange} />);

    await selectAll();
    await userEvent.click(screen.getByRole('button', { name: 'Link' }));
    await userEvent.type(screen.getByLabelText('Web or email address'), 'caldart.org/events');
    await userEvent.click(screen.getByRole('button', { name: 'Add link' }));

    expect(lastChange(handleChange)).toBe('<p><a href="https://caldart.org/events">Hello</a></p>');
  });

  it('puts the focus in the address box when the panel opens', async () => {
    render(<Harness initial="<p>Hello</p>" />);

    await userEvent.click(screen.getByRole('button', { name: 'Link' }));

    expect(screen.getByLabelText('Web or email address')).toHaveFocus();
  });

  it('writes the address itself as the link when nothing is selected', async () => {
    const handleChange = vi.fn();
    render(<Harness onChange={handleChange} />);

    await userEvent.click(area());
    await userEvent.click(screen.getByRole('button', { name: 'Link' }));
    await userEvent.type(screen.getByLabelText('Web or email address'), 'ops@caldart.org{Enter}');

    expect(lastChange(handleChange)).toBe(
      '<p><a href="mailto:ops@caldart.org">ops@caldart.org</a></p>',
    );
  });

  it('refuses an address that cannot be a link, and changes nothing', async () => {
    const handleChange = vi.fn();
    render(<Harness initial="<p>Hello</p>" onChange={handleChange} />);

    await selectAll();
    await userEvent.click(screen.getByRole('button', { name: 'Link' }));
    await userEvent.type(screen.getByLabelText('Web or email address'), 'javascript:alert(1)');
    await userEvent.click(screen.getByRole('button', { name: 'Add link' }));

    expect([screen.getByRole('alert').textContent, handleChange.mock.calls.length]).toEqual([
      LINK_ADDRESS_ERROR,
      0,
    ]);
  });

  it('offers the link it is on for editing, and removes it', async () => {
    const handleChange = vi.fn();
    render(
      <Harness initial='<p><a href="https://caldart.org">Hello</a></p>' onChange={handleChange} />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Link' }));
    expect(screen.getByLabelText('Web or email address')).toHaveValue('https://caldart.org');
    await userEvent.click(screen.getByRole('button', { name: 'Remove link' }));

    expect(lastChange(handleChange)).toBe('<p>Hello</p>');
  });

  it('closes the panel on Escape without changing anything', async () => {
    const handleChange = vi.fn();
    render(<Harness initial="<p>Hello</p>" onChange={handleChange} />);

    await userEvent.click(screen.getByRole('button', { name: 'Link' }));
    await userEvent.keyboard('{Escape}');

    expect([
      screen.queryByRole('region', { name: 'Link' }),
      handleChange.mock.calls.length,
    ]).toEqual([null, 0]);
  });
});

describe('RichTextEditor images', () => {
  const png = new File(['png'], 'plane.png', { type: 'image/png' });

  it('uploads the picked file, asks for a description, and puts the image in', async () => {
    const handleChange = vi.fn();
    const handleUploadImage = vi.fn(() => Promise.resolve(STORED));
    render(<Harness onChange={handleChange} onUploadImage={handleUploadImage} />);

    await userEvent.upload(screen.getByLabelText('Choose an image'), png);
    await userEvent.type(screen.getByLabelText(/Describe the image/), 'A Cessna on the ramp');
    await userEvent.click(screen.getByRole('button', { name: 'Put image in' }));

    expect([handleUploadImage.mock.calls, lastChange(handleChange)]).toEqual([
      [[png]],
      '<img src="https://caldart.example.org/media/bulk-email/abc.png" ' +
        'alt="A Cessna on the ramp" width="600" height="300"><p></p>',
    ]);
  });

  it('opens the file picker from the Image button', async () => {
    render(<Harness />);
    const picker = screen.getByLabelText<HTMLInputElement>('Choose an image');
    const click = vi.spyOn(picker, 'click');

    await userEvent.click(screen.getByRole('button', { name: 'Image' }));

    expect(click).toHaveBeenCalledOnce();
  });

  it('offers only image types in the picker', () => {
    render(<Harness />);

    expect(screen.getByLabelText('Choose an image')).toHaveAttribute(
      'accept',
      'image/png,image/jpeg,image/gif,image/webp',
    );
  });

  it('refuses to put an image in without a description', async () => {
    const handleChange = vi.fn();
    render(<Harness initial="<p>Hello</p>" onChange={handleChange} />);

    await userEvent.upload(screen.getByLabelText('Choose an image'), png);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Put image in' })).toBeEnabled());
    await userEvent.click(screen.getByRole('button', { name: 'Put image in' }));

    expect([screen.getByRole('alert').textContent, handleChange.mock.calls.length]).toEqual([
      IMAGE_ALT_ERROR,
      0,
    ]);
  });

  it('waits for the upload before the image can go in', async () => {
    render(<Harness onUploadImage={() => new Promise<UploadedImage>(() => undefined)} />);

    await userEvent.upload(screen.getByLabelText('Choose an image'), png);

    expect([
      screen.getByRole('status').textContent,
      screen.getByRole('button', { name: 'Put image in' }),
    ]).toEqual(['Uploading plane.png…', expect.objectContaining({ disabled: true })]);
  });

  it('says why an upload failed', async () => {
    render(
      <Harness
        onUploadImage={() => Promise.reject(new Error('Choose a PNG, JPEG, GIF, or WebP image.'))}
      />,
    );

    await userEvent.upload(screen.getByLabelText('Choose an image'), png);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Choose a PNG, JPEG, GIF, or WebP image.',
    );
  });

  it('keeps a small image at its own size', async () => {
    const handleChange = vi.fn();
    render(
      <Harness
        onChange={handleChange}
        onUploadImage={() => Promise.resolve({ ...STORED, width: 320, height: 200 })}
      />,
    );

    await userEvent.upload(screen.getByLabelText('Choose an image'), png);
    await userEvent.type(screen.getByLabelText(/Describe the image/), 'Logo{Enter}');

    expect(lastChange(handleChange)).toContain('width="320" height="200"');
  });
});
