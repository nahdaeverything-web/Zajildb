import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // VERBATIM COPIES. src/db/**, src/engine/**, src/i18n.js, src/dates.js and tests/*.test.js
    // are byte-identical copies of the root tree's files (see README, "Two files you did not
    // write"). The root is read-only during the port, so a lint finding in one of them is a
    // ROOT finding for ROOT-FINDINGS.md, not something to fix here — and linting them would
    // invite exactly the edit the isolation contract forbids. src/db/react.ts is NOT in this
    // list: it is the port's own code.
    "src/db/storage.js",
    "src/db/oplog.js",
    "src/db/records.js",
    "src/db/io.js",
    "src/db/sync.js",
    "src/engine/**",
    "src/i18n.js",
    "src/dates.js",
    "src/countries.js",
    "tests/*.test.js",
    "tests/harness.js",
    "tests/idmap.js",
    "sw/sw.template.js",
  ]),
  {
    // The port renders device-local blobs through object URLs, never a remote source, and
    // next.config.ts sets images.unoptimized because the default loader needs a server this
    // product does not have. `<img>` is the correct element here; next/image is not
    // available to it. Scoped to the files that actually show a photo.
    files: ["app/bird/view.tsx", "app/cert/view.tsx", "app/tools/view.tsx"],
    rules: { "@next/next/no-img-element": "off" },
  },
]);

export default eslintConfig;
