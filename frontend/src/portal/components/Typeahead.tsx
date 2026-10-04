/**
 * A text box that offers matches in a list under it as the person types.
 *
 * The box stays an ordinary controlled input: whatever is typed is the value,
 * and the list is only an offer.  Once the typing has settled for the debounce
 * wait and the text is at least `minLength` characters, `useSuggestions` is
 * asked for matches and they are listed under the box.  ArrowDown and ArrowUp
 * move through them, Enter or a click picks one, and Escape, a click outside,
 * or moving the focus away shuts the list.  A pick hands the item to `onPick`
 * and shuts the list until the person types again.
 *
 * The box is a combobox in the ARIA sense: the list is a listbox it controls,
 * the option under the arrow keys is its active descendant, and a status line
 * tells a screen reader how many suggestions there are.
 */
import { useCallback, useId, useRef, useState } from 'react';
import type { FocusEvent, JSX, KeyboardEvent } from 'react';

import { useClickOutside } from './useClickOutside';
import { useDebounced } from './useDebounced';

/** The part of a query result the typeahead reads: a `useQuery` result satisfies it. */
export interface SuggestionResults<T> {
  data: T[] | undefined;
}

export interface TypeaheadProps<T> {
  /** The box's `id`, which a `Field`'s label points at. */
  id: string;
  /** What the list is, for a screen reader, such as `Suggested addresses`. */
  listLabel: string;
  value: string;
  /** Called with the text on every keystroke. */
  onValueChange: (next: string) => void;
  /** Called with the item the person picked. */
  onPick: (item: T) => void;
  /**
   * The query hook behind the list.  It is handed the settled text, or an empty
   * string while the list is shut or the text is too short, and must stay idle
   * for an empty string.
   */
  useSuggestions: (term: string) => SuggestionResults<T>;
  /** A stable, unique key for an item. */
  itemKey: (item: T) => string;
  /** An item's text in the list. */
  itemLabel: (item: T) => string;
  /** Optional detail printed after the label in the muted face, such as a count. */
  itemMeta?: (item: T) => string;
  /** The fewest characters worth asking about; three unless given. */
  minLength?: number;
  /**
   * A line shown under the box when a search comes back empty, such as `No member matches
   * that.`; without it an empty answer shows nothing.
   */
  emptyText?: string;
  name?: string;
  autoComplete?: string;
  placeholder?: string;
  className?: string;
  onBlur?: () => void;
  'aria-describedby'?: string;
  'aria-invalid'?: boolean;
}

/** The fewest characters that narrow a search enough to be worth asking about. */
export const TYPEAHEAD_MIN_LENGTH: number = 3;

/**
 * A combobox that lists what `useSuggestions` finds for the settled text and
 * hands the one picked to `onPick`.
 */
export function Typeahead<T>({
  id,
  listLabel,
  value,
  onValueChange,
  onPick,
  useSuggestions,
  itemKey,
  itemLabel,
  itemMeta,
  minLength = TYPEAHEAD_MIN_LENGTH,
  emptyText,
  onBlur,
  ...input
}: TypeaheadProps<T>): JSX.Element {
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const rootRef = useRef<HTMLDivElement>(null);
  const listId = useId();

  const term = useDebounced(value.trim());
  const isAsking = isOpen && term.length >= minLength;
  const { data } = useSuggestions(isAsking ? term : '');
  const items = isAsking ? (data ?? []) : [];
  const isListShown = items.length > 0;
  const isEmptyShown = emptyText !== undefined && isAsking && data !== undefined && !isListShown;
  // A fresh answer can be shorter than the last, so an index past its end means none.
  const active = activeIndex < items.length ? activeIndex : -1;

  const handleClose = useCallback(() => {
    setIsOpen(false);
    setActiveIndex(-1);
  }, []);

  useClickOutside(rootRef, handleClose, isListShown);

  const handlePick = (item: T): void => {
    onPick(item);
    handleClose();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>): void => {
    if (!isListShown) {
      if (event.key === 'ArrowDown') setIsOpen(true);
      return;
    }
    const last = items.length - 1;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveIndex(active >= last ? 0 : active + 1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex(active <= 0 ? last : active - 1);
    } else if (event.key === 'Enter' && active >= 0) {
      // Picking, not submitting the form the box sits in.
      event.preventDefault();
      const item = items[active];
      if (item !== undefined) handlePick(item);
    }
  };

  const handleBlur = (event: FocusEvent<HTMLInputElement>): void => {
    const next = event.relatedTarget;
    if (!(next instanceof Node && rootRef.current?.contains(next) === true)) handleClose();
    onBlur?.();
  };

  const optionId = (index: number): string => `${listId}-option-${index}`;
  const count = items.length;

  return (
    <div className="typeahead" ref={rootRef}>
      <input
        {...input}
        id={id}
        type="text"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={isListShown}
        aria-controls={isListShown ? listId : undefined}
        aria-activedescendant={active >= 0 ? optionId(active) : undefined}
        value={value}
        onChange={(event) => {
          onValueChange(event.target.value);
          setIsOpen(true);
          setActiveIndex(-1);
        }}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
      />
      {isListShown ? (
        <ul id={listId} role="listbox" aria-label={listLabel} className="typeahead__list">
          {items.map((item, index) => (
            <li
              key={itemKey(item)}
              id={optionId(index)}
              role="option"
              aria-selected={index === active}
              tabIndex={-1}
              className={
                index === active
                  ? 'typeahead__option typeahead__option--active'
                  : 'typeahead__option'
              }
              // Keep the focus in the box, so the pick lands before the box's blur shuts the list.
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => handlePick(item)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') handlePick(item);
              }}
            >
              {itemLabel(item)}
              {itemMeta === undefined ? null : (
                <>
                  {' '}
                  <span className="typeahead__meta">{itemMeta(item)}</span>
                </>
              )}
            </li>
          ))}
        </ul>
      ) : null}
      {isEmptyShown ? <p className="muted typeahead__empty">{emptyText}</p> : null}
      <span className="visually-hidden" role="status">
        {isListShown
          ? `${count} ${count === 1 ? 'suggestion' : 'suggestions'}`
          : isEmptyShown
            ? emptyText
            : ''}
      </span>
    </div>
  );
}
