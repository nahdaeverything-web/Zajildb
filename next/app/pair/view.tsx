'use client';
import { useSearchParams } from 'next/navigation';

export default function View() {
  const id = useSearchParams().get('id');
  return <section style={{ padding: 24 }}><h1>الزوج</h1><p>Phase 0 placeholder — /pair?id={id ?? '—'}</p></section>;
}
