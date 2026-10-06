import { act, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { useRef, useState } from 'react';
import type { JSX } from 'react';
import { describe, expect, it } from 'vitest';

import { RichTextEditor } from '@/portal/components/RichTextEditor';
import type { RichTextEditorHandle } from '@/portal/components/RichTextEditor';
import { FIELDS } from '@test/fixtures/bulkEmail';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';

import { MessageFieldMenu, SUBJECT_MENU_NAME, SubjectFieldMenu } from './InsertFieldMenu';
import { useBulkEmailFields } from './richTextApi';

/** A subject input with its menu, and a message editor with its own in the toolbar. */
function Compose(): JSX.Element {
  const [subject, setSubject] = useState('Hello  pilots');
  const [body, setBody] = useState('<p>Dear </p>');
  const subjectRef = useRef<HTMLInputElement>(null);
  const editorRef = useRef<RichTextEditorHandle>(null);
  const fields = useBulkEmailFields();
  return (
    <>
      <label>
        Subject
        <input ref={subjectRef} value={subject} onChange={(e) => setSubject(e.target.value)} />
      </label>
      <SubjectFieldMenu subjectRef={subjectRef} onSubjectChange={(next) => setSubject(next)} />
      <RichTextEditor
        ref={editorRef}
        label="Message"
        value={body}
        onChange={(html) => setBody(html)}
        fields={fields.data}
        onUploadImage={() => Promise.reject(new Error('unused'))}
        toolbarExtra={<MessageFieldMenu editorRef={editorRef} />}
      />
      <output aria-label="Body">{body}</output>
    </>
  );
}

function answerFields(): void {
  server.use(http.get(`${API}/bulk-email/fields`, () => HttpResponse.json(FIELDS)));
}

async function choose(label: string, menu = 'Insert field'): Promise<void> {
  await userEvent.click(screen.getByRole('button', { name: menu }));
  await userEvent.click(await screen.findByRole('button', { name: new RegExp(`^${label}`) }));
}

describe('InsertFieldMenu', () => {
  it('lists every field by its label, with its description', async () => {
    answerFields();
    renderWithProviders(<Compose />);

    await userEvent.click(screen.getByRole('button', { name: 'Insert field' }));
    const choices = await screen.findAllByRole('button', { name: /person's/ });

    expect(choices.map((choice) => choice.textContent)).toEqual([
      "First nameThe person's first name.",
      "DARTThe name of the person's DART.",
    ]);
  });

  it("puts the message's field into the message as a chip", async () => {
    answerFields();
    renderWithProviders(<Compose />);

    await choose('First name');

    const message = screen.getByRole('textbox', { name: 'Message' });
    expect([
      message.querySelector('.rich-text__field')?.textContent,
      screen.getByRole('status', { name: 'Body' }).textContent,
    ]).toEqual(['First name', expect.stringContaining('{first_name}')]);
  });

  it("puts the subject's field into the subject at the cursor", async () => {
    answerFields();
    renderWithProviders(<Compose />);
    const subject = screen.getByRole<HTMLInputElement>('textbox', { name: 'Subject' });

    await userEvent.click(subject);
    act(() => subject.setSelectionRange(6, 6));
    await choose('First name', SUBJECT_MENU_NAME);

    expect([subject.value, subject.selectionStart]).toEqual(['Hello {first_name} pilots', 18]);
  });

  it("puts the message's field into the message even after the subject had the focus", async () => {
    answerFields();
    renderWithProviders(<Compose />);

    await userEvent.click(screen.getByRole('textbox', { name: 'Subject' }));
    await choose('DART');

    expect([
      screen.getByRole<HTMLInputElement>('textbox', { name: 'Subject' }).value,
      screen.getByRole('status', { name: 'Body' }).textContent,
    ]).toEqual(['Hello  pilots', expect.stringContaining('{dart_name}')]);
  });

  it('closes the menu once a field is chosen', async () => {
    answerFields();
    renderWithProviders(<Compose />);

    await choose('DART');

    expect(screen.queryByRole('group', { name: 'Fields' })).toBeNull();
  });

  it('says when the fields could not be loaded', async () => {
    server.use(http.get(`${API}/bulk-email/fields`, () => HttpResponse.json({}, { status: 500 })));
    renderWithProviders(<Compose />);

    await userEvent.click(screen.getByRole('button', { name: 'Insert field' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "The fields didn't load. Try again in a moment.",
    );
  });
});
