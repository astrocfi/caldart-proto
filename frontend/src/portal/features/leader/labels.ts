/** Human wording for the coded fields on a leader's status card (PLAN §4.2). */
import type { IfrRated, MedicalType, PilotCertificateType, Rating } from '../../api/types';

export const CERTIFICATE_LABELS: Record<PilotCertificateType, string> = {
  none: 'No certificate on file',
  student: 'Student',
  sport: 'Sport',
  recreational: 'Recreational',
  private: 'Private',
  commercial: 'Commercial',
  atp: 'Airline transport',
};

export const MEDICAL_LABELS: Record<MedicalType, string> = {
  none: 'No medical on file',
  basicmed: 'BasicMed',
  first: 'First class',
  second: 'Second class',
  third: 'Third class',
};

export const IFR_LABELS: Record<IfrRated, string> = {
  na: 'Not stated',
  yes: 'IFR',
  no: 'VFR only',
};

export const RATING_LABELS: Record<Rating, string> = {
  instrument: 'Instrument',
  multi_engine: 'Multi-engine',
  cfi: 'CFI',
  cfii: 'CFII',
  mei: 'MEI',
  seaplane: 'Seaplane',
  helicopter: 'Helicopter',
  glider: 'Glider',
};

export function ratingLabels(ratings: Rating[]): string {
  return ratings.map((rating) => RATING_LABELS[rating] ?? rating).join(', ');
}
