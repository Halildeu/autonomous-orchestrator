# Accounting Domain Rules

- Tekduzen Hesap Plani (Turkish Uniform Chart of Accounts) structure applies
- ACCOUNT_PLAN: hierarchical account structure (parent-child via account code prefixes)
- ACCOUNT_CARD: individual account records linked to plan
- ACCOUNT_CARD_ROWS: transaction detail rows per card
- BUDGET_PLAN_ROW: budget allocation per account per period
- Account codes: 3-digit main group, 5+ digit sub-accounts
- Fiscal year partitioning: yearly databases for transaction isolation
- Double-entry bookkeeping: every debit must have matching credit
- Currency handling: always store amount + currency_code + exchange_rate
- Decimal precision: 2 digits for display, 4+ digits for calculation
- Report templates: balance sheet, income statement, trial balance
- Audit trail: all accounting modifications must be logged with user + timestamp
