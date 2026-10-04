/**
 * The order the bulk email and callout tables leave columns out in when a screen is
 * too narrow for all of them (`dropOrder` on a `DataTable` column): the lowest goes
 * first, so who wrote an email, which matters most to CalDART management, stays
 * longest.
 */
export const DROP_ORDER = {
  chosenBy: 1,
  aircraft: 2,
  homeAirport: 3,
  type: 4,
  dart: 5,
  kind: 6,
  triedAt: 7,
  lastEdited: 8,
  from: 9,
} as const;
