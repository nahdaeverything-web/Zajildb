import { Suspense } from 'react';
import BirdsView from './view';
// الطيور — loft home. Spec: design/approved/loft-home-v1.html.
export default function Page() { return <Suspense fallback={null}><BirdsView /></Suspense>; }
