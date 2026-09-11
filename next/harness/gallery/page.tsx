import { Suspense } from 'react';
import GalleryView from './view';

// Fidelity gallery for the shared-states components. Build-gated exactly like
// the harness: next/harness/ is copied into app/test-harness/ by
// `npm run build:harness` and removed after, so this route never ships.
// Every state shared-states-v1 designs is rendered here for the screenshots
// in next/fidelity/shared-states/.
export default function GalleryPage() {
  return <Suspense fallback={null}><GalleryView /></Suspense>;
}
