import { t } from '@/src/i18n.ext.js';
import s from './shared.module.css';
// Page-level loading — shared-states §07: one spinner, one line, no grey skeletons.
export default function Loading({ label }: { label?: string }) {
  return <div className={s.pageload} data-testid="loading" role="status"><div className={s.spinner} aria-hidden="true" />{label ?? t('common.loading')}</div>;
}
