import path from 'node:path';
import fs from 'node:fs';
import {Config} from '@remotion/cli/config';

/**
 * TEMPORARY WORKAROUND -- Remotion 4.0.441 broken Headless Shell extraction.
 *
 * On this machine (Node 24, Windows), Remotion 4.0.441's automatic Chrome
 * Headless Shell download is broken: it extracts only 2 of the ~290 files in
 * the archive. `remotion render` then exits 0 and silently produces NO output
 * file. A manually extracted, known-good browser at the repo-root
 * `.browser-cache/` launches fine and renders correctly.
 *
 * This config points Remotion at that pre-extracted browser so the normal
 * `npx remotion render` CLI path works WITHOUT a `--browser-executable` flag.
 * Both `render_demo.py` and `tools/video/video_compose.py` invoke the CLI from
 * inside `remotion-composer/`, so this config is auto-discovered for both.
 *
 * Path resolution note: Remotion bundles this config with esbuild and `eval`s
 * it, so `__dirname` / `import.meta.url` point at the CLI's OWN dist directory
 * (`node_modules/@remotion/cli/dist`), NOT this file. Verified empirically:
 * resolving the browser path from `__dirname` yields
 * `node_modules/@remotion/cli/.browser-cache/...`, which does not exist -- so
 * the `existsSync` guard below would miss and Remotion would silently fall back
 * to the broken auto-download. We therefore resolve from `process.cwd()`
 * instead. Remotion can only run with its working directory at this composer
 * root (it requires `tsconfig.json` here and refuses to start otherwise), and
 * every project caller (render_demo.py, tools/video/video_compose.py, the
 * package.json scripts) invokes it from here -- so `process.cwd()` is reliably
 * this directory (remotion-composer/). We resolve relative to that -- never an
 * absolute hardcoded path.
 *
 * REMOVE this override once Remotion's bundled Headless Shell extraction is
 * fixed (or the project pins a Remotion version whose download works on
 * Node 24). Until then the override is required for rendering to produce output.
 */
const composerDir = process.cwd();
const browserExecutable = path.resolve(
  composerDir,
  '..',
  '.browser-cache',
  'chrome-headless-shell-win64',
  'chrome-headless-shell.exe',
);

if (fs.existsSync(browserExecutable)) {
  Config.setBrowserExecutable(browserExecutable);
} else {
  // Fail loud rather than silently rendering nothing (the exact failure mode
  // this workaround exists to prevent).
  console.warn(
    `[remotion.config] WARNING: pre-extracted browser not found at ${browserExecutable}. ` +
      'Falling back to Remotion\'s auto-downloaded browser, which is known broken on ' +
      'Node 24 with Remotion 4.0.441 (extracts 2/290 files -> silent empty render).',
  );
}
