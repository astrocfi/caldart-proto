/**
 * `/admin/aircraft/:id` — one record: edit it, read its history, see who flies
 * it, delete it.
 */
import { useState } from 'react';
import type { JSX } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import type { AircraftPatch } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { DeleteButton } from '@/portal/components/DeleteButton';
import { EmptyState } from '@/portal/components/EmptyState';
import { Page } from '@/portal/components/Page';
import { StatusChip } from '@/portal/components/StatusChip';
import { useToast } from '@/portal/components/Toast';
import { AircraftForm } from '@/portal/features/aircraft/AircraftForm';
import { InsuranceChip } from '@/portal/features/aircraft/InsuranceChip';
import { ServiceChip } from '@/portal/features/aircraft/ServiceChip';
import {
  useAircraft,
  useAircraftChanges,
  useDeleteAircraft,
  useUpdateAircraft,
} from '@/portal/features/aircraft/api';
import { aircraftToValues } from '@/portal/features/aircraft/form';
import { changeLine, lastUpdatedLine } from './history';
import '@/portal/features/aircraft/aircraft.css';
import './history.css';

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
  const [confirming, setConfirming] = useState(false);

  if (knownId && record.isPending) {
    return (
      <Page title="Aircraft" eyebrow="Administration">
        <p className="muted" role="status">
          Loading…
        </p>
      </Page>
    );
  }

  if (!knownId || record.isError || !record.data) {
    const missing = !knownId || (record.error instanceof ApiError && record.error.status === 404);
    return (
      <Page title="Aircraft" eyebrow="Administration">
        <EmptyState
          title={missing ? 'No such aircraft' : 'That record could not be loaded'}
          description={
            missing
              ? 'It may have been deleted from the register.'
              : (record.error as Error)?.message
          }
          action={
            <Link className="button button--secondary" to="/admin/aircraft">
              Back to the register
            </Link>
          }
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

  const handleDelete = (): void => {
    remove.mutate(undefined, {
      onSuccess: () => {
        toast.show(`${aircraft.n_number} deleted from the register.`, 'success');
        void navigate('/admin/aircraft');
      },
      onError: (error) => toast.show(error.message, 'error'),
    });
  };

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
      return <p className="muted">That record's history could not be loaded.</p>;
    }
    if (changes.data.length === 0) {
      return <p className="muted">No change is recorded for this record.</p>;
    }
    return (
      <ul className="aircraft-history">
        {changes.data.map((change) => (
          <li key={change.id}>{changeLine(change)}</li>
        ))}
      </ul>
    );
  };

  return (
    <Page
      title={aircraft.n_number}
      eyebrow="Aircraft record"
      lede={`${aircraft.make} ${aircraft.model}`.trim()}
      actions={
        <>
          <InsuranceChip aircraft={aircraft} />
          <ServiceChip aircraft={aircraft} />
        </>
      }
    >
      <Card
        eyebrow={lastUpdatedLine(aircraft.updated_at, aircraft.updated_by ?? null)}
        title="Details"
      >
        <AircraftForm
          key={aircraft.id}
          initial={aircraftToValues(aircraft)}
          submitLabel="Save changes"
          pending={update.isPending}
          serverErrors={serverErrors}
          onSubmit={handleSave}
          withAdminFields
        />
      </Card>

      <Card eyebrow="Register" title="History">
        {history()}
      </Card>

      <Card eyebrow="Members" title="Pilots who fly this aircraft">
        {pilots.length === 0 ? (
          <p className="muted">No member lists this aircraft on their profile.</p>
        ) : (
          <ul className="aircraft-pilots">
            {pilots.map((pilot) => (
              <li key={pilot.user_id}>
                <Link to={`/admin/members/${pilot.user_id}`}>{pilot.name}</Link>
                <span className="aircraft-pilots__email mono">{pilot.email}</span>
                <StatusChip
                  tone={pilot.membership_status === 'current' ? 'current' : 'expired'}
                  label={
                    pilot.membership_status === 'current' ? 'Member current' : 'Member expired'
                  }
                />
                <StatusChip
                  tone={pilot.medical_is_current ? 'current' : 'expired'}
                  label={pilot.medical_is_current ? 'Medical current' : 'Medical not current'}
                />
              </li>
            ))}
          </ul>
        )}
      </Card>

      <div className="aircraft-danger">
        {confirming ? (
          <div className="cluster">
            <p className="field__error" role="alert">
              Delete {aircraft.n_number} permanently? It will disappear from every member's profile.
            </p>
            <Button variant="danger" disabled={remove.isPending} onClick={handleDelete}>
              {remove.isPending ? 'Deleting…' : 'Yes, delete it'}
            </Button>
            <Button variant="quiet" onClick={() => setConfirming(false)}>
              Keep it
            </Button>
          </div>
        ) : (
          <DeleteButton
            label="Delete this aircraft"
            variant="danger"
            small={false}
            onClick={() => setConfirming(true)}
          >
            Delete this aircraft
          </DeleteButton>
        )}
      </div>
    </Page>
  );
}
