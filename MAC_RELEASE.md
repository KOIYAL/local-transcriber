# Mac release checklist

This project ships the macOS app as a signed and notarized DMG for distribution
outside the Mac App Store.

## Build machine

- macOS on Apple Silicon or Intel
- Xcode Command Line Tools
- Python 3.10 or newer
- Node.js and npm
- Apple Developer Program membership
- Developer ID Application certificate installed in the login keychain

Apple's Developer ID guidance says apps distributed outside the Mac App Store
should be signed so Gatekeeper can verify the developer, and macOS Mojave or
newer users gain additional confidence when the software is notarized:
https://developer.apple.com/developer-id/

## One-time notarization setup

Create a notarytool keychain profile on the build Mac:

```bash
xcrun notarytool store-credentials "koiyal-notary"
```

Use an App Store Connect API key or Apple ID credentials when prompted. Apple
notes that custom build workflows should use `xcrun notarytool`, and `xcrun
stapler` can attach the notarization ticket to packages such as DMGs:
https://developer.apple.com/developer-id/

## Release build

```bash
export MAC_CODESIGN_IDENTITY="Developer ID Application: 株式会社KOIYAL (TEAMID)"
export MAC_NOTARY_PROFILE="koiyal-notary"
./build-macos.sh
```

The script creates:

```text
dist/electron/LocalTranscriber-darwin-<arch>/LocalTranscriber.app
dist/LocalTranscriber-macOS-<arch>.dmg
```

Unsigned builds are only for local testing. Public downloads should use the
signed and notarized DMG.

## Pre-release test pass

- Open the DMG on a clean Mac user account.
- Drag the app to Applications.
- Launch from Applications, not from the DMG.
- Confirm first setup downloads the model.
- Transcribe at least one short audio file.
- Export TXT, SRT, VTT, and JSON.
- Quit and reopen the app to confirm the model is reused.
- Test both Japanese and English UI.

## Distribution notes

- Publish the DMG, not the unpacked `.app` bundle.
- Keep `START_HERE_MAC.txt` in the DMG.
- Keep Windows Store/MSIX submission assets separate from the Mac DMG flow.
- Mac App Store distribution is a separate track and needs App Sandbox-specific
  work before submission.
