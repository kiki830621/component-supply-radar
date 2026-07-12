## ADDED Requirements

### Requirement: Local DuckDB is the writable authority
The system SHALL store permitted normalized observations in one local DuckDB database. All observation timestamps MUST use UTC and all prices MUST use fixed precision decimal values with an ISO 4217 currency code.

#### Scenario: Permitted Future observation is stored
- **WHEN** Future returns a permitted observation for `BAT54STA`
- **THEN** DuckDB stores regional available inventory, factory inventory, quantity on order, minimum quantity, order multiple, normalized lead-time days, lifecycle, currency, and every price break

### Requirement: Observation writes are transactional and idempotent
The system SHALL derive a deterministic ingestion hash from canonical normalized content. Reprocessing identical content MUST NOT create duplicate observations or price breaks.

#### Scenario: Batch partially fails validation
- **WHEN** one observation in a database transaction violates a storage constraint
- **THEN** the transaction writes none of that transaction's observations or price breaks
- **THEN** the collection run records the validation failure

### Requirement: Collection runs are distinguishable from zero inventory
The system SHALL record each source run with start time, completion time, request count, success count, failure count, and `success`, `partial`, or `failed` status. A failed request MUST NOT create a zero-inventory observation.

#### Scenario: Source is unavailable
- **WHEN** every Future request fails before returning valid data
- **THEN** the run status is `failed`
- **THEN** no zero-valued observation is inserted for the requested parts

### Requirement: Secrets and generated data remain outside Git
The system MUST load credentials from environment variables or an ignored local environment file. It SHALL NOT place keys, authorization headers, real databases, Parquet files, logs, real watchlists, or generated reports in tracked Git files.

#### Scenario: Repository secret scan
- **WHEN** the tracked repository is scanned after a daily run
- **THEN** no Future license key or MotherDuck token is present

### Requirement: Weekly Parquet backups are bounded and self-describing
The system SHALL create weekly Parquet backups containing schema version and export time. It SHALL retain the latest 12 complete weekly backup snapshots and remove older complete snapshots.

#### Scenario: Thirteenth successful backup
- **WHEN** a thirteenth complete weekly backup is created
- **THEN** exactly the 12 newest complete backup snapshots remain
