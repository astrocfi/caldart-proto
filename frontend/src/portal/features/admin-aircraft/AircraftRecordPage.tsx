/**
 * `/admin/aircraft/:id` — one record: edit it, see who flies it, delete it.
 */
import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { ApiError } from '../../api/client';
import type { AircraftPatch } from '../../api/types';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { Page } from '../../components/Page';
import { StatusChip } from '../../components/StatusChip';
import { useToast } from '../../components/Toast';
import { InsuranceChip } from '../aircraft/InsuranceChip';
import { ServiceChip } from '../aircraft/ServiceChip';
import '../aircraft/aircraft.css';
import { useAircraft, useDeleteAircraft, useUpdateAircraft } from '../aircraft/api';
import { aircraftToValues } from '../aircraft/form';
import { AircraftForm } from '../aircraft/AircraftForm';

export function AircraftRecordPage() {
  const { id } = useParams<{ id: string }>();
  // `:id` matches any path segment, so `/admin/aircraft/abc` reaches this
  // page.  Treat an id that is not a record id as a record that is not there,
  // rather than asking the server about `NaN`.
  const aircraftId = Number(id);
  const knownId = Number.isInteger(aircraftId) && aircraftId > 0;
  const navigate = useNavigate();
  const toast = useToast();

  const record = useAircraft(knownId ? aircraftId : null);
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

  const save = (payload: AircraftPatch): void => {
    update.mutate(payload, {
      onSuccess: (saved) => toast.show(`${saved.n_number} saved.`, 'success'),
    });
  };

  const destroy = (): void => {
    remove.mutate(undefined, {
      onSuccess: () => {
        toast.show(`${aircraft.n_number} deleted from the register.`, 'success');
        navigate('/admin/aircraft');
      },
      onError: (error) => toast.show((error as Error).message, 'error'),
    });
  };

  const serverErrors = update.error instanceof ApiError ? update.error.fieldErrors : undefined;

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
      <Card eyebrow="Register" title="Details">
        <AircraftForm
          key={aircraft.id}
          initial={aircraftToValues(aircraft)}
          submitLabel="Save changes"
          pending={update.isPending}
          serverErrors={serverErrors}
          onSubmit={save}
          withAdminFields
        />
      </Card>

      <Card eyebrow="Members" title="Pilots who fly this aircraft">
        {pilots.length === 0 ? (
          <p className="muted">No member lists this aircraft on their profile.</p>
        ) : (
          <ul className="aircraft-pilots">
            {pilots.map((pilot) => (
              <li key={pilot.user_id}>
                <span>{pilot.name}</span>
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
            <Button variant="danger" disabled={remove.isPending} onClick={destroy}>
              {remove.isPending ? 'Deleting…' : 'Yes, delete it'}
            </Button>
            <Button variant="quiet" onClick={() => setConfirming(false)}>
              Keep it
            </Button>
          </div>
        ) : (
          <Button variant="danger" onClick={() => setConfirming(true)}>
            Delete this aircraft
          </Button>
        )}
      </div>
    </Page>
  );
}
