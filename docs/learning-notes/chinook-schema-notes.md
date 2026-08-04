# Chinook schema note

The `data/chinook.db` file here uses the sqlitetutorial.net redistribution of
Chinook, which renames tables to lowercase/snake_ish (`invoice_items`,
`playlist_track`) instead of the original lerocha/chinook-database repo's
PascalCase (`InvoiceLine`). This is the standard public dataset, unmodified
otherwise — the renaming is upstream, not a cleaning step done in this
project. Ground-truth SQL in Phase 5's eval set must use these actual table
names (`invoice_items`, not `InvoiceLine`).
