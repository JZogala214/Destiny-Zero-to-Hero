# Destiny Zero to Hero

A Windows desktop app that tracks a "Zero to Hero" raid run in Destiny 2. It
rolls random ability unlocks and raid weapons from encounter loot tables,
including randomized perk rolls generated from a bundled Bungie manifest.

The executable includes a snapshot of the manifest, so the app does not
require a Bungie API key or network connection to start.

## Local data

Save data and downloaded icons are stored in `%APPDATA%\Destiny Zero to Hero`.
The bundled manifest is read-only application data. No Bungie account sign-in
or account data is stored by this application.

## Third-party content

The app redistributes a snapshot of Bungie's manifest and downloads Bungie
icon content at runtime.

## License

Original project code is available under the MIT License; see [LICENSE](LICENSE).
Third-party content and attribution notes are documented in [NOTICE.md](NOTICE.md).
