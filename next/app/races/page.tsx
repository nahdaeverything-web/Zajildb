import { Suspense } from 'react';
import View from './view';

export default function Page() {
  return <Suspense fallback={null}><View /></Suspense>;
}
