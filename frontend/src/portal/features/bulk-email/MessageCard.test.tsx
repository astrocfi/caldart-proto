import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { useState } from 'react';
import type { JSX } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { FIELDS } from '@test/fixtures/bulkEmail';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
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
  return (
    <MessageCard
      subject={subject}
      body={body}
      onSubjectChange={(next) => setSubject(next)}
      onBodyChange={(next) => {
        setBody(next);
        handleBody(next);
      }}
      saveState="idle"
      errors={errors}
      isEditable={isEditable}
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
    renderWithProviders(<Card errors={{ body: '{nickname} is not a recipient field.' }} />);
    const message = screen.getByRole('textbox', { name: 'Message' });
    expect([screen.getByRole('alert').textContent, message.getAttribute('aria-invalid')]).toEqual([
      '{nickname} is not a recipient field.',
      'true',
    ]);
  });

  it('holds the message still, without Insert field, once it cannot change', () => {
    answerFields();
    renderWithProviders(<Card isEditable={false} />);
    expect([
      screen.getByRole('textbox', { name: 'Message' }).getAttribute('contenteditable'),
      screen.queryByRole('button', { name: 'Insert field' }),
    ]).toEqual(['false', null]);
  });
});
