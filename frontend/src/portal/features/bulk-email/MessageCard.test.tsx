import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { useRef, useState } from 'react';
import type { JSX } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { FIELDS } from '@test/fixtures/bulkEmail';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { RichTextEditorHandle } from '@/portal/components/RichTextEditor';
import { MessageCard } from './MessageCard';

interface CardProps {
  errors?: { subject?: string; body?: string };
  isEditable?: boolean;
  onBodyChange?: (body: string) => void;
}

/** The card holding its own subject and message, as the compose screen does. */
function Card({
  errors = {},
  isEditable = true,
  onBodyChange: handleBody = () => undefined,
}: CardProps): JSX.Element {
  const [subject, setSubject] = useState('Hangar day');
  const [body, setBody] = useState('<p>Dear </p>');
  const subjectRef = useRef<HTMLInputElement>(null);
  const editorRef = useRef<RichTextEditorHandle>(null);
  return (
    <MessageCard
      emailId={7}
      emailType={1}
      emailTypeName="Operational"
      isCallout={false}
      closesAt={null}
      subject={subject}
      body={body}
      replyTo="grace@example.org"
      defaultReplyTo="grace@example.org"
      onSubjectChange={(next) => setSubject(next)}
      onBeforeTest={() => Promise.resolve(true)}
      onBodyChange={(next) => {
        setBody(next);
        handleBody(next);
      }}
      saveState="idle"
      errors={errors}
      isEditable={isEditable}
      onBeforeReplace={() => Promise.resolve(true)}
      onReplaced={() => undefined}
      subjectRef={subjectRef}
      editorRef={editorRef}
    />
  );
}

function answerFields(): void {
  server.use(http.get(`${API}/bulk-email/fields`, () => HttpResponse.json(FIELDS)));
}

describe('MessageCard', () => {
  it('writes the message in the rich text editor', () => {
    answerFields();
    renderWithProviders(<Card />);
    expect(screen.getByRole('textbox', { name: 'Message' })).toHaveAttribute(
      'contenteditable',
      'true',
    );
  });

  it('puts a field into the message from Insert field', async () => {
    answerFields();
    const handleBody = vi.fn();
    renderWithProviders(<Card onBodyChange={handleBody} />);
    await userEvent.click(screen.getByRole('button', { name: 'Insert field' }));
    await userEvent.click(await screen.findByRole('button', { name: /^First name/ }));
    expect(handleBody).toHaveBeenLastCalledWith(expect.stringContaining('{first_name}'));
  });

  it("shows the server's refusal of the message beside it", () => {
    answerFields();
    renderWithProviders(<Card errors={{ body: '{nickname} is not one of the fields.' }} />);
    const message = screen.getByRole('textbox', { name: 'Message' });
    expect([screen.getByRole('alert').textContent, message.getAttribute('aria-invalid')]).toEqual([
      '{nickname} is not one of the fields.',
      'true',
    ]);
  });

  it('says how to deal with an unknown field the message shows as a chip', () => {
    answerFields();
    renderWithProviders(
      <Card
        errors={{
          body:
            '{nickname} is not one of the fields. Pick a field from Insert field, or take out ' +
            'the braces.',
        }}
      />,
    );
    expect(screen.getByRole('alert')).toHaveTextContent(
      '{nickname} is not one of the fields. Delete it, or click it to choose a field.',
    );
  });

  it('holds the message still, without Insert field, once it cannot change', () => {
    answerFields();
    renderWithProviders(<Card isEditable={false} />);
    expect([
      screen.getByRole('textbox', { name: 'Message' }).getAttribute('contenteditable'),
      screen.queryByRole('button', { name: 'Insert field' }),
    ]).toEqual(['false', null]);
  });

  it('asks where replies go, between the subject and the message', () => {
    answerFields();
    renderWithProviders(<Card />);
    expect(screen.getByRole('textbox', { name: 'Reply-To' })).toHaveValue('grace@example.org');
  });

  it('offers Send me a test while the email can change', () => {
    answerFields();
    renderWithProviders(<Card />);
    expect(screen.getByRole('button', { name: 'Send me a test' })).toBeEnabled();
  });

  it('offers no test once the email cannot change', () => {
    answerFields();
    renderWithProviders(<Card isEditable={false} />);
    expect(screen.queryByRole('button', { name: 'Send me a test' })).toBeNull();
  });
});
