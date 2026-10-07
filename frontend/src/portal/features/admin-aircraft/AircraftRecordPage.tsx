/**
 * `/admin/aircraft/:id` — one record: edit it, verify its insurance, read its
 * history, see who flies it, delete it.
 *
 * The marks follow the aircraft check: the header's insurance reads *Not verified* for a
 * current policy nobody has checked, and each pilot carries the member check's GO or
 * NO-GO, so the record never clears what a check would not.
 */
import { useState } from 'react';
import type { JSX } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import type { AircraftPatch, MembershipState } from '@/portal/api/types';
import { Card } from '@/portal/components/Card';
import { DeleteButton } from '@/portal/components/DeleteButton';
import { EmptyState } from '@/portal/components/EmptyState';
import { Page } from '@/portal/components/Page';
import { StatusDot } from '@/portal/components/StatusDot';
import type { StatusTone } from '@/portal/components/StatusDot';
import { useToast } from '@/portal/components/Toast';
import { AircraftForm } from '@/portal/features/aircraft/AircraftForm';
import { ServiceDot } from '@/portal/features/aircraft/ServiceDot';
import {
  useAircraft,
  useAircraftChanges,
  useDeleteAircraft,
  useUpdateAircraft,
} from '@/portal/features/aircraft/api';
import { aircraftToValues } from '@/portal/features/aircraft/form';
import { InsuranceCheckDot } from '@/portal/features/leader/AircraftStatusCard';
import { GoMark, isReady } from '@/portal/features/leader/LeaderLookup';
import { InsuranceVerificationCard } from '@/portal/features/verification/InsuranceVerificationCard';
import { changeLine, lastUpdatedLine } from './history';
import '@/portal/features/aircraft/aircraft.css';
import './history.css';
import './record.css';

/** An email address with a line-break opportunity before its @, its only good place. */
function EmailWithBreak({ email }: { email: string }): JSX.Element {
  const at = email.indexOf('@');
  if (at <= 0) return <>{email}</>;
  return (
    <>
      {email.slice(0, at)}
      <wbr />
      {email.slice(at)}
    </>
  );
}

/** How the pilot list names each membership state: a friend is a friend, never expired. */
const PILOT_MEMBERSHIP: Record<MembershipState, { tone: StatusTone; label: string }> = {
  current: { tone: 'current', label: 'Member current' },
  expired: { tone: 'expired', label: 'Member expired' },
  friend: { tone: 'none', label: 'Friend' },
  none: { tone: 'none', label: 'Not yet paid' },
  donor: { tone: 'none', label: 'Donor' },
};

/** `/admin/aircraft/:id` page: edit, view pilots, and delete an aircraft record. */
export function AircraftRecordPage(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  // `:id` matches any path segment, so `/admin/aircraft/abc` reaches this
  // page.  Treat an id that is not a record id as a record that is not there,
  // rather than asking the server about `NaN`.
  const aircraftId = Number(id);
  const knownId = Number.isInteger(aircraftId) && aircraftId > 0;
  const navigate = useNavigate();
  const toast = useToast();

  const record = useAircraft(knownId ? aircraftId : null);
  const changes = useAircraftChanges(knownId ? aircraftId : null);
  const update = useUpdateAircraft(aircraftId);
  const remove = useDeleteAircraft(aircraftId);
  // Bumped only when the insurance panel saves, so the Details form starts again
  // from the corrected record; an unrelated write (someone else's edit, a
  // background refetch) must not discard whatever the admin is mid-typing there.
  const [formResetKey, setFormResetKey] = useState(0);

  if (knownId && record.isPending) {
    return (
      <Page title="Aircraft">
        <p className="muted" role="status">
          Loading…
        </p>
      </Page>
    );
  }

  if (!knownId || record.isError || !record.data) {
    const missing = !knownId || (record.error instanceof ApiError && record.error.status === 404);
    return (
      <Page title="Aircraft">
        <EmptyState
          title={missing ? 'No such aircraft' : "That record didn't load"}
          description={
            missing
              ? 'It may have been deleted from the register.'
              : (record.error as Error)?.message
          }
          action={<Link to="/admin/aircraft">Back to aircraft</Link>}
        />
      </Page>
    );
  }

  const aircraft = record.data;
  // Absent for a caller without a leader or administrator role.
  const pilots = aircraft.pilots ?? [];

  const handleSave = (payload: AircraftPatch): void => {
    update.mutate(payload, {
      onSuccess: (saved) => toast.show(`${saved.n_number} saved.`, 'success'),
    });
  };

  const handleDelete = (): Promise<void> =>
    remove.mutateAsync(undefined).then(
      () => {
        toast.show(`${aircraft.n_number} deleted from the register.`, 'success');
        void navigate('/admin/aircraft');
      },
      (error: Error) => toast.show(error.message, 'error'),
    );

  const serverErrors = update.error instanceof ApiError ? update.error.fieldErrors : undefined;

  // An audit card must never present a history it does not have as an empty
  // one: a request still in flight or a request that failed each say so.
  const history = (): JSX.Element => {
    if (changes.isPending) {
      return (
        <p className="muted" role="status">
          Loading…
        </p>
      );
    }
    if (changes.isError || changes.data === undefined) {
      return (
        <p className="muted">That record's history didn&apos;t load. Try again in a moment.</p>
      );
    }
    if (changes.data.length === 0) {
      return <p className="muted">No change is recorded for this record.</p>;
    }
    return (
      <ul className="record-history">
        {changes.data.map((change) => (
          <li key={change.id}>{changeLine(change)}</li>
        ))}
      </ul>
    );
  };

  return (
    <Page
      title={aircraft.n_number}
      tabTitle={`${aircraft.n_number} · Aircraft record`}
      lede={`${aircraft.make} ${aircraft.model}`.trim()}
      actions={
        <>
          <InsuranceCheckDot
            aircraft={aircraft}
            verified={aircraft.insurance_verification.verified}
          />
          <ServiceDot aircraft={aircraft} />
          <Link to="/admin/aircraft">Back to aircraft</Link>
        </>
      }
    >
      <InsuranceVerificationCard
        aircraft={aircraft}
        onSaved={() => setFormResetKey((key) => key + 1)}
      />

      <Card title="Details">
        {/* The line would contradict a history that records no change, so it waits for one. */}
        {(changes.data?.length ?? 0) > 0 ? (
          <p className="muted">
            {lastUpdatedLine(aircraft.updated_at, aircraft.updated_by ?? null)}
          </p>
        ) : null}
        <AircraftForm
          // A verification save may correct the insurance, so it starts the form
          // again from what the register now holds; any other write to the
          // record -- someone else's edit, a background refetch -- must not
          // discard an edit in progress here.
          key={`${aircraft.id}-${formResetKey}`}
          initial={aircraftToValues(aircraft)}
          submitLabel="Save changes"
          pending={update.isPending}
          serverErrors={serverErrors}
          serverError={update.error}
          onSubmit={handleSave}
          withAdminFields
        />
      </Card>

      <Card title="History">{history()}</Card>

      <Card title="Pilots who fly it">
        {pilots.length === 0 ? (
          <p className="muted">No member lists this aircraft on their profile.</p>
        ) : (
          <ul className="aircraft-pilots">
            {pilots.map((pilot) => {
              // The member check's own verdict, so the record and both checks agree.
              const ready = isReady(pilot.go_no_go);
              return (
                <li key={pilot.user_id}>
                  <Link to={`/admin/members/${pilot.user_id}`}>{pilot.name}</Link>
                  <span className="aircraft-pilots__email">
                    <EmailWithBreak email={pilot.email} />
                  </span>
                  <StatusDot
                    tone={PILOT_MEMBERSHIP[pilot.membership_status].tone}
                    label={PILOT_MEMBERSHIP[pilot.membership_status].label}
                  />
                  <GoMark go={ready} label={ready ? 'Cleared to fly' : 'Not cleared to fly'} />
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      <div className="aircraft-danger">
        <DeleteButton
          label="Delete this aircraft"
          variant="danger"
          small={false}
          warning={`Delete ${aircraft.n_number} permanently? It will disappear from every member's profile.`}
          onDelete={handleDelete}
        >
          Delete this aircraft
        </DeleteButton>
      </div>
    </Page>
  );
}
