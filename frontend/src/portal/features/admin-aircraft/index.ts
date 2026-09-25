export { AircraftRegisterPage } from './AircraftRegisterPage';
export { AircraftRecordPage } from './AircraftRecordPage';
// The form itself is shared with `/profile/aircraft`, so it lives in
// `features/aircraft`; re-exported here for the screens that had it.
export { AircraftForm } from '@/portal/features/aircraft/AircraftForm';
export type { AircraftFormProps } from '@/portal/features/aircraft/AircraftForm';
