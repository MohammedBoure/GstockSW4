# StockLam to GstockSW4 migration verification

Date: 2026-07-27

## Scope

- Source repository: `D:\git\StockLam`, `main`, final SHA `0b458cd`.
- Source migration range: `591aa10..0b458cd`, 19 commits from 2026-07-16 through 2026-07-27.
- Target repository: `D:\git\GstockSW4`, `main`.
- The verified prior migration baseline `migration/stocklam-20260714-15` at `b9b6af3` was merged into target main with merge commit `d3d9cba`; target commit `d4544ff` remained in the merge history.
- Implementation SHA: `1f93525`; verification record initially committed at `131cd1d` and finalized in the current branch.

The migration was semantic. Target-specific sales, cashier, receipt, barcode, PDF, configuration, and runtime behavior were retained. Source cleanup deletions were not replayed, including deletion candidates such as `config.json`, `pdf_settings.json`, `index.html`, `fix.py`, `fix2.py`, POS/receipt/barcode editors, and `user_session.json`.

## Implemented groups

1. `5eaa0d0` and `439fc21`: AI demand forecasting, expiry-risk analysis, waste anomaly detection, and the `AiAnalyticsTab` integrated into the existing analysis tabs without a new permission.
2. `8800476`: packaged mobile API startup hardening, reusable API port, request diagnostics, and smaller PyInstaller collection rules.
3. `94e0bc0`: filtered available-stock totals, low-stock-only dashboard alerts, detailed consumption filters, movement-log pagination/filter APIs, and repeat-safe permission/schema behavior that extends existing Admin permissions instead of resetting them.
4. `cb7c5f5`: independent reclamation navigation and permission, canonical `ui/widgets/reclamation`, canonical `ui/widgets/inventaire` with old paths retained, active history date/search filters while preserving POS `Sale`/`Sale_Return`, None/null reclamation filtering, and batch reclamation click/icon behavior.
5. `469e9e6`: whitespace normalization for migrated UI files.
6. `1f93525`: ModernStock launcher resource copied from the existing ModernStock logo so the Android release manifest resolves `@mipmap/ic_launcher`.

## Validation evidence

Passed:

- `git diff --check`.
- Conflict-marker scan: no `<<<<<<<`, `=======`, or `>>>>>>>` markers.
- `python -m compileall -q database ui tools ai main.py test pyinstaller.py`.
- `python -m unittest discover -s test`: 12 tests passed, including AI and mobile API coverage.
- Mobile API tests: health, discovery, authorization, and remote-scan paths passed.
- Flutter 3.44.0: `flutter analyze` reported no issues.
- Flutter widget tests: all tests passed.
- `flutter build apk --release`: passed after adding the tracked ModernStock launcher resource; output was `mobile_inventory_scanner/build/app/outputs/flutter-apk/app-release.apk` (65.6 MB).
- `git status --short --branch`: clean and aligned with `origin/main` at the final push.

Not runnable in this execution environment:

- PySide6 offscreen widget creation: the active Python runtime has no `PySide6` or `qtawesome` installation.
- Isolated live MySQL migration/row-count/admin-permission repetition: the active runtime has no `mysql.connector` and no live database connection was available. The initializer code was kept idempotent by its duplicate-object handling, and Admin permission initialization now performs a JSON union of missing keys rather than replacing existing custom permissions; this still requires a MySQL-backed acceptance run on the deployment environment.
- Manual POS, reclamation, inventory, history, reports, AI, and phone-LAN walkthroughs require the desktop dependencies, configured database, and connected device.

## Git and data safety

- Every migration group was committed with author `MohammedBoure` and pushed to the target `origin` remote.
- No hard reset was used.
- `user_session.json` was not added or committed.
- The existing target-only configuration and business modules were left in place; the Android icon is the only binary resource explicitly added for the release build.
