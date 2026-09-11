import { Suspense } from 'react';
import View from '../form';

export default function Page() {
  return <Suspense fallback={null}><View /></Suspense>;
}
