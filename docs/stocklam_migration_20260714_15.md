# StockLam to GstockSW4 migration record (2026-07-14 to 2026-07-15)

## Pinned inputs and safety points

- Source: `D:/git/StockLam`, `main` pinned at `591aa106b45ea234e960c44bc7046f2fd4772b58`.
- Target baseline: `D:/git/GstockSW4`, `main` pinned at `d4544ff`.
- Safety snapshot: `backup/gstocksw4-pre-stocklam-20260715` at `04a5319` (pushed to `origin`).
- Migration branch: `migration/stocklam-20260714-15`.
- Existing GstockSW4 direct batch add/edit, supplier filter, location selection and `quick_add_dialog.py` were preserved in `194fe56` before the StockLam features were applied.
- Temporary `tools/patches/` content stayed only in the safety branch. Production copies of `fix.py` and `fix2.py` were preserved.

## Source commit coverage

| Source commit | Source feature | Target commit(s) | Verification |
|---|---|---|---|
| `87a1fd3` | Configurable PDF stamp library | `ee96af0` | Local-settings tests, stamp CRUD on isolated DB clone, PySide6 import smoke |
| `78d723f` | Per-user local settings and standalone PDF dialog | `ee96af0` | User isolation and legacy-file migration tests |
| `8e8765d` | Stamp anchoring to first signature space | `ee96af0` | Python compilation and PDF module import smoke |
| `81680dc` | Separate local/DB PDF saves and full-screen dialog | `ee96af0` | Local-store tests and settings import smoke |
| `fbd0671` | LAN barcode bridge and UDP discovery | `dc15e05` | HTTP health and UDP discovery unit tests |
| `817b24f` | Final ModernStock scanner UI and camera switching | `dc15e05` | `flutter analyze`, widget test and release APK build |
| `04281ed` | Camera lifecycle/startup fixes | `dc15e05` | `flutter analyze`, widget test and release APK build |
| `11e9e88` | Android camera compatibility | `dc15e05` | Android release APK build |
| `fc3b1ed` | Android release camera initialization | `dc15e05` | Android release APK build |
| `1be8da9` | Deliver scans to active desktop field | `dc15e05` | Remote-scan callback and authorization unit tests |
| `77bda1a` | Route scans to inventory input | `dc15e05` | Remote-scan callback test and PySide6 import smoke |
| `bb5f5f6` | Mobile integration, reclamations, alerts and PO workflow | `dc15e05`, `ee96af0`, `37b1d43` | HTTP tests, schema clone, PO/stamp CRUD, Python compile/import smoke |
| `20589fc` | Ignore rules | `b556238` | Union review and `git diff --check` |
| `591aa10` | PDF package organization, inventory sessions and source lot selection | `ee96af0`, `4deceb3` | Schema clone, Python compile/import smoke and column-index review |

All 14 source commits are represented. The migration was semantic; no source commit was cherry-picked and no divergent GstockSW4 file was replaced wholesale.

## Preserved GstockSW4 behavior

- POS, sales history, caisse sessions, annual invoice sequences and `Print_Templates` remain in the schema, backup order and codebase.
- Receipt and barcode visual editors remain alongside the new PDF configuration launcher.
- Direct inventory batch add/edit, `Supplier_ID`, supplier filtering and location selection remain present.
- Normal external transfers and Bon de Retour partner scoping remain present; source-lot selection uses `Quantity_Current` for output and `Available_To_Return` for returns.
- Inventory export and cancellation remain available with their original permissions; session deletion uses `act_inventory_cancel`.

## Automated acceptance evidence

- Python 3.14: full `compileall` passed for `database`, `ui`, `tools`, `main.py` and `test`.
- Python unittest: 8 tests passed (health, remote scan, missing-key authorization, UDP discovery and four local-settings cases).
- PySide6: affected application, settings, PDF, procurement, inventory and billing modules imported successfully with `QT_QPA_PLATFORM=offscreen`.
- Flutter: `flutter analyze` reported no issues; widget test passed; release APK built successfully (62.8 MB).
- Database: a complete 40-table JSONL/schema ZIP backup was created before testing. A temporary database clone was migrated twice with no unexpected schema warnings and then removed.
- Database preservation: all original table row counts matched after cleanup. The checked baseline included 406 products, 540 batches, 14 sales invoices, 3 caisse sessions, 2 print templates, 3 inventory sessions, 43 purchase orders, 248 PO lines and one sales sequence row.
- Compatibility: existing `Show_In_Alerts` values were preserved; a simulated legacy table without the column enabled its existing products once, while new products defaulted to `FALSE`.
- CRUD: stamp add/update/activate/delete and incremental PO header/line add/update/delete passed on the isolated clone.
- Git: conflict-marker scan and `git diff --check` passed.
- Coverage: all 52 paths changed by the 14 source commits are represented in the target diff; no source path is missing from the migration branch.

## Manual acceptance still required before fast-forwarding main

The migration branch must not be fast-forwarded to `main` until these physical/interactive checks are completed:

1. Run the release app against a controlled copy and visually verify PDF, printer, barcode and receipt settings together; generate sale, PO and reception PDFs with and without banner/stamp.
2. Exercise reclamation, quick add, supplier filter, inventory export/cancel/delete and both transfer types with multiple lots.
3. Complete a POS sale, receipt preview/print, caisse open/close and sales-history review.
4. Test the release APK on a physical phone: discovery, camera switching, active-field delivery, inventory fallback and restart behavior.

Until those checks pass, `main` remains at `d4544ff`; only the safety and migration branches are pushed.
