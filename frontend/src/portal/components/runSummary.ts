/**
 * Words shared by every scheduled run's report: the sentence naming what a
 * run sent or would send, and the reason breakdown underneath it. The
 * reminders, renewals and scheduled-reports panels of `/portal/system`, and
 * the DART rosters card of `/admin/reports`, all read a run this way.
 */

/** The counts a run result carries that a one-line summary needs. */
interface RunCounts {
  sent: number;
  skipped: number;
}

/** The sentence shown after a run: what it sent, or would send, and how much it skipped. */
export function runSummary(result: RunCounts, dryRun: boolean): string {
  const verb = dryRun ? 'Would send' : 'Sent';
  const emails = result.sent === 1 ? '1 email' : `${result.sent} emails`;
  return `${verb} ${emails}, skipped ${result.skipped}.`;
}

/**
 * `Skipped: <reason> <count>, …`, one entry per reason a candidate was passed
 * over that occurred at least once, or `''` when nothing was skipped.
 *
 * The labeled reasons come first, in `labels`' order; a reason the server
 * reports that `labels` does not name follows by its raw slug, so a new
 * reason still shows up here rather than silently dropping out of the total.
 * `labels` names the run's own vocabulary of skip reasons.
 */
export function skippedBreakdown(
  byReason: Record<string, number>,
  labels: Record<string, string>,
): string {
  const labeled = Object.keys(labels)
    .filter((reason) => (byReason[reason] ?? 0) > 0)
    .map((reason) => `${labels[reason]} ${byReason[reason]}`);
  const unlabeled = Object.keys(byReason)
    .filter((reason) => !(reason in labels) && (byReason[reason] ?? 0) > 0)
    .map((reason) => `${reason} ${byReason[reason]}`);
  const parts = [...labeled, ...unlabeled];
  return parts.length > 0 ? `Skipped: ${parts.join(', ')}.` : '';
}
