/**
 * What a form does when it refuses a submit: the focus moves to the first highlighted
 * field, and one line beside the submit button says how many fields to check.
 *
 * A long form's errors appear beside their fields, often a screen or more above the
 * button the person pressed.  Moving the focus takes a keyboard or screen reader user
 * to the first of them, scrolling it into view takes a sighted one there too, and the
 * line by the button tells a person who scrolls back down that the form is still
 * waiting on them.  Server field errors also go once the person edits the field they
 * name, so a corrected box stops saying it is wrong.
 */
import { useEffect, useState } from 'react';
import type { JSX, RefObject } from 'react';

import { countInvalidFields, focusRefusal } from './focus';

export interface RefusedSubmit {
  /** How many fields are highlighted since the last refusal; 0 hides the line. */
  count: number;
  /** Call when the form refuses a submit on its own rules, before it sends anything. */
  refuse: () => void;
}

/**
 * Watch the form in `formRef` for refused submits.
 *
 * A refusal is either a call to `refuse` (the form's own rules found a problem) or a
 * `serverError` that is not null (the server sent one back; pass the mutation's
 * `error`, whose identity changes with every failed request).  After either, once the
 * highlighted fields have rendered, the focus moves to the first of them, or to the
 * form's `role="alert"` message when no field is highlighted.  From then on `count`
 * follows the number of fields still marked `aria-invalid="true"`, so the line beside
 * the button shrinks as the person corrects them and goes when none is left.
 */
export function useRefusedSubmit(
  formRef: RefObject<HTMLElement | null>,
  serverError?: unknown,
): RefusedSubmit {
  const [attempt, setAttempt] = useState(0);
  const [isWatching, setIsWatching] = useState(false);
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (attempt === 0) return;
    setCount(focusRefusal(formRef.current));
    setIsWatching(true);
  }, [attempt, formRef]);

  useEffect(() => {
    if (serverError === null || serverError === undefined) return;
    setCount(focusRefusal(formRef.current));
    setIsWatching(true);
  }, [serverError, formRef]);

  // A field's error may go as the person edits it, or another may appear, so the count
  // is read again whenever a field's `aria-invalid` changes or a field comes or goes.
  useEffect(() => {
    const form = formRef.current;
    if (!isWatching || form === null) return undefined;
    const observer = new MutationObserver(() => setCount(countInvalidFields(form)));
    observer.observe(form, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ['aria-invalid'],
    });
    return () => observer.disconnect();
  }, [isWatching, formRef]);

  return { count, refuse: () => setAttempt((current) => current + 1) };
}

/**
 * The line beside a form's submit button after a refused submit: "Check the
 * highlighted field." for one, "Check the 3 highlighted fields." for more, and
 * nothing at all when `count` is 0.
 */
export function RefusedSubmitNote({ count }: { count: number }): JSX.Element | null {
  if (count === 0) return null;
  return (
    <p className="form-refusal" role="status">
      {count === 1 ? 'Check the highlighted field.' : `Check the ${count} highlighted fields.`}
    </p>
  );
}

/**
 * `errors` without the ones for fields edited since `source` arrived.
 *
 * `source` is what the errors came from, normally a mutation's `error`: a new value
 * means new errors, and starts again from the `values` of that render.  A key of
 * `errors` that is also a key of `values` is dropped once `values[key]` differs from
 * what it was then; any other key, such as `detail` or a nested `contacts.0.phone`,
 * stays until the next `source`.  A `source` of `undefined` keeps every error, for a
 * caller that does not say where its errors came from.
 */
export function useFreshErrors<Errors extends Partial<Record<string, string | null>>>(
  source: unknown,
  values: object,
  errors: Errors,
): Errors {
  const [snapshot, setSnapshot] = useState({ source, values });
  let current = snapshot;
  if (source !== undefined && !Object.is(snapshot.source, source)) {
    current = { source, values };
    setSnapshot(current);
  }
  const before = current.values as Record<string, unknown>;
  const now = values as Record<string, unknown>;
  if (source === undefined) return errors;
  // A subset of a map of optional messages is still such a map.
  return Object.fromEntries(
    Object.entries(errors).filter(([key]) => !(key in now) || Object.is(now[key], before[key])),
  ) as Errors;
}
