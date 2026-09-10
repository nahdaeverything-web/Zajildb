import { Suspense } from 'react';
import HarnessView from './view';

// Test harness — NEVER in a shipped build. This file lives in next/harness/
// and is copied to app/test-harness/page.tsx only by `npm run build:harness`,
// which removes it again when the build ends. Two guards enforce that: the
// prebuild guard fails a normal build if app/test-harness/ exists, and the
// postbuild guard fails it if out/test-harness.html was produced.
// (Not __harness: the App Router excludes underscore-prefixed folders from routing.).
export default function HarnessPage() {
  return <Suspense fallback={null}><HarnessView /></Suspense>;
}
