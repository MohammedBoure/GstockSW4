# StockLam Feature Gap Report

Source reference: `D:\git\StockLam` on `main`.
Target project: `D:\git\GstockSW4` on `main`.

## Implemented in this pass

- Bon de Retour / subcontractor return flow:
  - `External_Transfer_Log.Transfer_Type` now supports `Outbound`, `Return`, `Free`, and `Paid`.
  - `External_Transfer_Log.Ref_Transfer_ID` is available for linking a return note to the originating transfer.
  - Returnable batches are scoped by partner through `get_returnable_batches_for_partner`.
  - Return quantities use `Available_To_Return`.
  - The invoice editor locks the return partner and rejects batches outside the allowed return set.
  - `Transfer_Return` movement logs were added while preserving GstockSW4 `Sale` and `Sale_Return`.

- Company/PDF settings:
  - Added `Company_Settings` schema support.
  - Added `CompanySettingsManager`.
  - Added the visual PDF editor dialog.
  - `PdfConfigWidget` now uses `data_manager.company_settings` when available, with local JSON fallback compatibility.

- Auto-backup retention:
  - Added `auto_backup_max_files` to settings UI.
  - `AutoBackupWorker` passes the configured retention limit to the backup manager.
  - Automatic backup cleanup now deletes only the oldest files needed to keep the configured maximum.

- Reception repair tools:
  - Updated `complete_reception_repair.py` from StockLam.
  - Updated `tools/repair_reception_stock_consistency.py` from StockLam.
  - Existing GstockSW4 stock display already had the important repaired-split behavior: `Quantity_Initial` is aggregated by internal barcode while the per-reception value remains available as `Reception_Quantity_Initial`.

## StockLam items intentionally not copied

- Secrets and local runtime files:
  - `.env`
  - `access_MySQL`
  - `config.json`
  - `user_session.json`
  - `commit_msg` / `commit_msgs`

- Generated reports and local outputs:
  - `reports/*.xlsx`

- Mobile companion project:
  - `mobile_inventory_scanner/`
  - GstockSW4 already has the matching desktop API server in `tools/inventory_mobile_api.py` and `main.py`.
  - The Flutter project can be imported later as a separate scoped task.

## GstockSW4 behavior preserved

- Sales/client modules remain in place:
  - `Clients`
  - `Sales_Invoices`
  - `Sales_Details`
  - `Client_Payments`
  - `Client_Credit_Notes`
  - `Client_Credit_Note_Details`

- Stock movement enum still supports:
  - `Sale`
  - `Sale_Return`

- Pricing fields on products and batches remain in the schema and inventory UI.

## Follow-up checks

- Manually test a Bon de Retour from an existing outbound transfer:
  - partner is auto-selected and locked;
  - only returnable batches for that partner appear;
  - quantities cannot exceed `Available_To_Return`;
  - movement history shows `Transfer_Return`.

- Manually test PDF settings:
  - save settings to `Company_Settings`;
  - reopen settings and confirm values reload from DB;
  - open the visual editor and confirm it updates the same settings.

- Manually test auto backup retention:
  - set max files to a small number;
  - force or wait for backups;
  - confirm only the oldest auto backups are removed.
