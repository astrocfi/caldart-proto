/**
 * Change what a standing authority charges.
 *
 * For an automatic renewal that is the plan and the contribution beside it; for a
 * recurring donation, the amount and how often.  It offers the same choosers the
 * setup flows do, so a member changes their mind in the words they made it up in.
 * A renewal's dues are not settable: every charge takes the chosen plan's price on
 * the day.
 *
 * The day of the next charge is the member's own, and the form opens on the day
 * the mandate already carries, or on today when that day has gone by without the
 * charge being taken.  A charge already scheduled keeps its own day, so a day set
 * while one is waiting is the day of the charge after it.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import type { MandateScope } from '@/portal/api/queries';
import type { MandateCadence, RenewalMandate, RenewalPatchRequest } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { todayIso } from '@/portal/components/DateText';
import { EmptyState } from '@/portal/components/EmptyState';
import { Field } from '@/portal/components/Field';
import { formatCents } from '@/portal/components/Money';
import { useToast } from '@/portal/components/Toast';
import { CadenceChooser } from '@/portal/features/checkout/CadenceChooser';
import { ContributionChooser } from '@/portal/features/checkout/ContributionChooser';
import { PlanChooser } from '@/portal/features/checkout/PlanChooser';
import { usePaymentsConfig } from '@/portal/features/checkout/api';
import { useUpdateRenewal } from './api';
import { notBeforeToday } from './chargeDate';
import { CADENCE_PHRASES } from './labels';
import '@/portal/features/checkout/checkout.css';

export interface RenewalChangeFormProps {
  /** The automatic renewal or the recurring donation. */
  scope: MandateScope;
  mandate: RenewalMandate;
  /** Called once the change is saved, or abandoned. */
  onDone: () => void;
}

/** The choosers over a mandate, saved with `PATCH /me/renewal` or `/me/donation`. */
export function RenewalChangeForm({
  scope,
  mandate,
  onDone: handleDone,
}: RenewalChangeFormProps): JSX.Element {
  const { data: config, isPending } = usePaymentsConfig();
  const earliestChargeOn = todayIso();
  const [plan, setPlan] = useState<string | null>(mandate.plan);
  const [nextChargeOn, setNextChargeOn] = useState(() => notBeforeToday(mandate.next_charge_on));
  const [contributionCents, setContributionCents] = useState(mandate.contribution_cents);
  const [cadence, setCadence] = useState<MandateCadence>(mandate.cadence);
  // Null until the member picks: the amount they already hold decides which
  // control shows it, so an amount no tier matches opens its own box.
  const [isOther, setIsOther] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const update = useUpdateRenewal(scope);
  const toast = useToast();

  if (isPending) {
    return (
      <p className="muted" role="status">
        Loading payment options…
      </p>
    );
  }

  if (!config) {
    return (
      <EmptyState
        title="Payment options could not be loaded"
        description="Please reload the page, or contact CalDART if it keeps happening."
      />
    );
  }

  const isDonation = scope === 'donation';

  // A membership that never expires cannot renew itself, so it is never offered.
  const renewable = config.plans.filter((entry) => entry.duration_days !== null);
  const offered = renewable.map((entry) => entry.slug);
  const chosenPlan = plan !== null && offered.includes(plan) ? plan : (offered[0] ?? null);

  const showsOther =
    isOther ??
    (contributionCents > 0 &&
      !config.contribution_tiers.some((tier) => tier.cents === contributionCents));

  // The server refuses a donation of nothing, so it is stopped here rather than
  // at the API.
  const needsContribution = isDonation && contributionCents === 0;
  // An empty box is valid HTML, and an empty date is not a date the API takes, so
  // the form waits for one rather than sending it.
  const needsChargeDate = nextChargeOn === '';

  async function save(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setError(null);
    const request: RenewalPatchRequest = {
      contribution_cents: contributionCents,
      next_charge_on: nextChargeOn,
    };
    if (isDonation) request.cadence = cadence;
    else if (chosenPlan !== null) request.plan = chosenPlan;
    try {
      await update.mutateAsync(request);
      toast.show('Changes saved.', 'success');
      handleDone();
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? (caught.fieldErrors.contribution_cents ??
              caught.fieldErrors.next_charge_on ??
              caught.fieldErrors.cadence ??
              caught.fieldErrors.plan ??
              caught.fieldErrors.auto_renew ??
              caught.message)
          : 'That change could not be saved.',
      );
    }
  }

  const planCents = renewable.find((entry) => entry.slug === chosenPlan)?.price_cents ?? 0;

  return (
    <form className="renewal__change stack" onSubmit={(event) => void save(event)}>
      <h3 className="eyebrow">
        {isDonation ? 'Change your recurring donation' : 'Change your renewal'}
      </h3>

      {!isDonation && chosenPlan !== null ? (
        <PlanChooser plans={renewable} value={chosenPlan} onChange={(next) => setPlan(next)} />
      ) : null}

      <ContributionChooser
        tiers={config.contribution_tiers}
        value={contributionCents}
        maxCents={config.max_contribution_cents}
        onChange={(next) => setContributionCents(next)}
        isOther={showsOther}
        // codespell:ignore-next-line onother
        onOther={(next) => setIsOther(next)}
      />

      {isDonation ? <CadenceChooser value={cadence} onChange={(next) => setCadence(next)} /> : null}

      <Field label="Next charge on">
        {(props) => (
          <input
            {...props}
            type="date"
            required
            min={earliestChargeOn}
            value={nextChargeOn}
            onChange={(event) => setNextChargeOn(event.target.value)}
          />
        )}
      </Field>

      <p className="renewal-setup__total">
        {isDonation ? (
          <>
            CalDART will charge <strong className="mono">{formatCents(contributionCents)}</strong>{' '}
            {CADENCE_PHRASES[cadence]}.
          </>
        ) : (
          <>
            Each year CalDART will charge{' '}
            <strong className="mono">{formatCents(planCents + contributionCents)}</strong> — the
            plan price on the day, plus your contribution.
          </>
        )}
      </p>

      {needsContribution ? (
        <p className="renewal-setup__blocked" role="status">
          Choose an amount to give.
        </p>
      ) : null}

      {needsChargeDate ? (
        <p className="renewal-setup__blocked" role="status">
          Choose the day of the next charge.
        </p>
      ) : null}

      {error ? (
        <p className="renewal__error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="cluster">
        <Button type="submit" disabled={update.isPending || needsContribution || needsChargeDate}>
          {update.isPending ? 'Saving…' : 'Save changes'}
        </Button>
        <Button variant="quiet" onClick={handleDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
