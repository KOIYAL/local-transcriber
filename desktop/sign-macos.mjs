// Developer ID signing for the packaged app (used by build-macos.sh when
// MAC_CODESIGN_IDENTITY is set). Electron Packager no longer signs: the
// backend's symbolic links must be fixed first (relativize_backend_links.py),
// and any change after signing would break the seal. @electron/osx-sign walks
// every binary in the bundle, including the PyInstaller backend in Resources.
//
// Usage: node desktop/sign-macos.mjs <app> <identity> <entitlements.plist>
import { sign } from "@electron/osx-sign";

const [app, identity, entitlements] = process.argv.slice(2);
if (!app || !identity || !entitlements) {
  console.error("Usage: node desktop/sign-macos.mjs <app> <identity> <entitlements.plist>");
  process.exit(2);
}
await sign({
  app,
  identity,
  // Same as the former --osx-sign.hardenedRuntime / entitlements /
  // entitlements-inherit options of Electron Packager.
  optionsForFile: () => ({ hardenedRuntime: true, entitlements }),
});
console.log(`Signed ${app} as ${identity}`);
