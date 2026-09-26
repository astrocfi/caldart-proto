/**
 * The shapes every report shares in the portal: which reports exist, the filter
 * fields each one takes.  What `GET /reports` says about them is `ReportSummary`
 * in `@/portal/api/types`, which the server's schema holds to account.
 *
 * A report's filters are declared once, as `FilterField`s in `./definitions`,
 * and the one `FilterBar` draws them wherever the report is filtered: its list
 * page and the form that subscribes somebody to it.
 */
import type { Choice } from '@/portal/choices';

/** The slug of every report the server's registry holds. */
export type ReportSlug =
  'members' | 'aircraft' | 'payments' | 'reconciliation' | 'contributions' | 'emails';

/** A download's format, which is also the extension of the file it names. */
export type ReportFormat = 'csv' | 'pdf';

/**
 * How a filter field is drawn and when it applies.
 *
 * - `search`: a text box, applied once the typing pauses;
 * - `select`: a drop-down whose first option is blank, meaning "any";
 * - `multiselect`: a list box six rows tall that takes several choices, sent as
 *   their values joined with commas in the order the box lists them; choosing
 *   none means "any";
 * - `number`: a box that holds digits only, applied once the typing pauses;
 * - `date`: a date picker, sent as `YYYY-MM-DD`;
 * - `toggle`: a checkbox that sends `true` when ticked and nothing when not.
 */
export type FilterKind = 'search' | 'select' | 'multiselect' | 'number' | 'date' | 'toggle';

/** One choice a `select` field offers: the value sent and the words shown. */
export type Option = Choice<string>;

/** One filter a report takes, named by the query parameter it sends. */
export interface FilterField {
  /** The query parameter, exactly as the report's endpoints read it. */
  key: string;
  label: string;
  kind: FilterKind;
  /**
   * A `select` or `multiselect` field's choices; `FilterBar`'s `options` prop can
   * supply or replace them.
   */
  options?: readonly Option[];
  /** A text box's placeholder, or the words on a `select` field's blank first option. */
  placeholder?: string;
  hint?: string;
  /**
   * A `number` field whose parameter is cents but which is typed and shown in
   * whole dollars.
   */
  isDollars?: boolean;
  /** Offered only where a subscription is set up, never on the report's list page. */
  subscriptionOnly?: boolean;
}

/** What the portal knows about one report: its name, filters, and what it allows. */
export interface ReportDefinition {
  slug: ReportSlug;
  label: string;
  filters: readonly FilterField[];
  /** Whether the report's columns can be chosen; a fixed report refuses `?columns=`. */
  choosable: boolean;
  /** Whether the report accepts `?period=` in place of concrete dates. */
  periods: boolean;
}

/** Filter values as the URL carries them: every value a string, an empty one unset. */
export type FilterValues = Record<string, string>;
