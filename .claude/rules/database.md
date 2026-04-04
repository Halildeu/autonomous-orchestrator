# Database Domain Rules

- Workcube ERP 3-tier schema: shared > company > yearly databases
- DashboardQueryEngine (report-service): NO alias on source table, use bare column names
- DashboardQueryEngine: qualify all ambiguous columns with table prefix
- SchemaLens API (port 8096) for Workcube table discovery — use it before writing queries
- Core accounting tables: ACCOUNT_PLAN, ACCOUNT_CARD, ACCOUNT_CARD_ROWS, BUDGET_PLAN_ROW
- Mali yil (fiscal year) based partition rules apply to yearly databases
- Transaction management: explicit BEGIN/COMMIT boundaries for multi-table operations
- Migration safety: always provide rollback scripts alongside forward migrations
- Never DROP TABLE without explicit backup/archive step
- Index naming: IX_{TableName}_{ColumnName} convention
- Foreign key naming: FK_{SourceTable}_{TargetTable} convention
- Always test queries against shared tier before company/yearly tiers
- Connection pooling: respect pool size limits in service configuration
