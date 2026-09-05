/**
 * The payment enums as this screen names them.
 *
 * The wording itself is the portal's shared vocabulary (`@/portal/choices`),
 * so the member's dashboard, their administrator's ledger and the per-member
 * payments tab cannot disagree about what "succeeded" is called.
 */
export {
  PAYMENT_PROVIDER_LABELS as PROVIDER_LABELS,
  PAYMENT_STATUS_LABELS as STATUS_LABELS,
  PAYMENT_WALLET_LABELS as WALLET_LABELS,
} from '../../choices';
export { paymentStatusTone as statusTone } from '../../components/StatusChip';
