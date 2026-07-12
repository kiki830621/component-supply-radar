## ADDED Requirements

### Requirement: Reports expose pressure, breadth, coverage, and provenance
The system SHALL produce an HTML summary and UTF-8 CSV detail file for each report run. Reports MUST include observation time in `Asia/Taipei`, source attribution, category intensity, breadth, alert state, coverage, and data sufficiency.

#### Scenario: Insufficient category data
- **WHEN** a category result is insufficient
- **THEN** HTML and CSV label it `unknown` or `insufficient`
- **THEN** neither output substitutes a zero-pressure value

### Requirement: MotherDuck publication is one-way and policy-gated
The system SHALL publish permitted normalized tables from local DuckDB to MotherDuck in one direction. It MUST exclude any source whose active policy has `cloud_share_allowed = false`.

#### Scenario: MotherDuck token is absent
- **WHEN** an operator runs the daily workflow without `MOTHERDUCK_TOKEN`
- **THEN** local collection, storage, analysis, report generation, and backup remain operational
- **THEN** the run reports that cloud publication was skipped

#### Scenario: Cloud sharing is disabled for a source
- **WHEN** a stored source policy has `cloud_share_allowed = false`
- **THEN** no observation or price break from that source is published to MotherDuck

### Requirement: Cloud publication failure does not corrupt local authority
The system SHALL treat MotherDuck as a read-only sharing copy. A publication failure MUST leave local DuckDB unchanged and MUST surface a nonzero sync result or a partial daily-run status.

#### Scenario: MotherDuck is unavailable
- **WHEN** local analysis succeeds and MotherDuck publication fails
- **THEN** local observations and reports remain complete
- **THEN** the workflow surfaces the publication failure

### Requirement: Native Windows scheduling is repeatable
The system SHALL provide PowerShell scripts that install, query, and remove a current-user Windows Scheduled Task for the daily workflow. The task MUST NOT store a Windows password, and generated logs MUST be written under an ignored local data directory.

#### Scenario: Scheduler removal
- **WHEN** the operator runs the uninstall command
- **THEN** the `ComponentSupplyRadar-Daily` task is removed if present
- **THEN** the application, DuckDB, configuration, reports, logs, and backups remain unchanged

#### Scenario: Installation is repeated
- **WHEN** the operator reruns the Windows installer or scheduled-task installer
- **THEN** locked dependencies and the task definition are refreshed
- **THEN** existing `.env`, `data\\watchlist.csv`, DuckDB, reports, logs, and backups are preserved
