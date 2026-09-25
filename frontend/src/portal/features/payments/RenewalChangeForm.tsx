/**
 * Change what a standing authority charges: the plan, and the contribution.
 *
 * It offers the same choosers the setup flow does, so a member changes their
 * mind in the words they made it up in.  The dues themselves are not settable:
 * every charge takes the chosen plan's price on the day.
 *
 * What the form may change comes from the authority itself rather than from the
 * screen around it: an authority that names no plan renews nothing, so no plan
 * is offered and none is sent.
 *
 * The day of the next charge is the member's own, and the form opens on the day
 * the mandate already carries.  A charge already scheduled keeps its own day, so
 * moving the date inside the notice window moves the charge after it.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import type { RenewalMandate, RenewalPatchRequest } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { EmptyState } from '@/portal/components/EmptyState';
import { Field } from '@/portal/components/Field';
import { formatCents } from '@/portal/components/Money';
import { useToast } from '@/portal/components/Toast';
import { ContributionChooser } from '@/portal/features/checkout/ContributionChooser';
import { PlanChooser } from '@/portal/features/checkout/PlanChooser';
import { usePaymentsConfig } from '@/portal/features/checkout/api';
import { useUpdateRenewal } from './api';
import { todayIso } from './chargeDate';
import '@/portal/features/checkout/checkout.css';

export interface RenewalChangeFormProps {
  mandate: RenewalMandate;
  /** True for a life member: their membership does not renew, so no plan is offered. */
  isLifetime: boolean;
  /** Called once the change is saved, or abandoned. */
  onDone: () => void;
}

/** The plan and contribution choosers over a mandate, saved with `PATCH /me/renewal`. */
export function RenewalChangeForm({
  mandate,
  isLifetime,
  onDone: handleDone,
}: RenewalChangeFormProps): JSX.Element {
  const { data: config, isPending } = usePaymentsConfig();
  const earliestChargeOn = todayIso();
  const [plan, setPlan] = useState<string | null>(mandate.plan);
  const [nextChargeOn, setNextChargeOn] = useState(mandate.next_charge_on ?? earliestChargeOn);
  const [contributionCents, setContributionCents] = useState(mandate.contribution_cents);
  // Null until the member picks: the amount they already hold decides which
  // control shows it, so an amount no tier matches opens its own box.
  const [isOther, setIsOther] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const update = useUpdateRenewal();
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

  // An authority that names no plan charges the contribution alone, whatever
  // the membership query happens to know: the mandate cannot disagree with
  // itself, and the server refuses a plan from it.
  const isContributionOnly = mandate.kind === 'contribution';
  const sendsPlan = !isContributionOnly && !isLifetime;

  // A membership that never expires cannot renew itself, so it is never offered.
  const renewable = config.plans.filter((entry) => entry.duration_days !== null);
  const offered = renewable.map((entry) => entry.slug);
  const chosenPlan = plan !== null && offered.includes(plan) ? plan : (offered[0] ?? null);

  const showsOther =
    isOther ??
    (contributionCents > 0 &&
      !config.contribution_tiers.some((tier) => tier.cents === contributionCents));

  // The server refuses an authority with nothing to charge, so a member whose
  // authority is a contribution alone is stopped here rather than at the API.
  const needsContribution = isContributionOnly && contributionCents === 0;

  async function save(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setError(null);
    const request: RenewalPatchRequest = {
      contribution_cents: contributionCents,
      next_charge_on: nextChargeOn,
    };
    if (sendsPlan && chosenPlan !== null) request.plan = chosenPlan;
    try {
      await update.mutateAsync(request);
      toast.show('Contribution saved.', 'success');
      handleDone();
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? (caught.fieldErrors.contribution_cents ??
              caught.fieldErrors.next_charge_on ??
              caught.fieldErrors.plan ??
              caught.fieldErrors.auto_renew ??
              caught.message)
          : 'That change could not be saved.',
      );
    }
  }

  const planCents = renewable.find((entry) => entry.slug === chosenPlan)?.price_cents ?? 0;
  const chargeCents = sendsPlan ? planCents + contributionCents : contributionCents;

  return (
    <form className="renewal__change stack" onSubmit={(event) => void save(event)}>
      <h3 className="eyebrow">
        {isContributionOnly ? 'Change your contribution' : 'Change your renewal'}
      </h3>

      {sendsPlan && chosenPlan !== null ? (
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

      <Field label="Next charge on">
        {(props) => (
          <input
            {...props}
            type="date"
            min={earliestChargeOn}
            value={nextChargeOn}
            onChange={(event) => setNextChargeOn(event.target.value)}
          />
        )}
      </Field>

      <p className="renewal-setup__total">
        Each year CalDART will charge <strong className="mono">{formatCents(chargeCents)}</strong>
        {sendsPlan
          ? ' — the plan price on the day, plus your contribution.'
          : ' for your contribution.'}
      </p>

      {needsContribution ? (
        <p className="renewal-setup__blocked" role="status">
          Choose a contribution to charge each year.
        </p>
      ) : null}

      {error ? (
        <p className="renewal__error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="cluster">
        <Button type="submit" disabled={update.isPending || needsContribution}>
          {update.isPending ? 'Saving…' : 'Save changes'}
        </Button>
        <Button variant="quiet" onClick={handleDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
