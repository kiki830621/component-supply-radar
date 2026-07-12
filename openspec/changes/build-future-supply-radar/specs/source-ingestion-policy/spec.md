## ADDED Requirements

### Requirement: Future Electronics is the sole automated distributor source
The system SHALL collect automated distributor observations only from the Future Electronics Product Info API in the first release. The system SHALL NOT implement Mouser collection, website scraping, catalog enumeration, automated ordering, or stock trading.

#### Scenario: Daily automated collection
- **WHEN** an operator runs the daily workflow with a valid Future API key
- **THEN** the system queries only configured Future Electronics manufacturer part numbers
- **THEN** the system performs no Mouser or website request

### Requirement: Collection is limited to a versioned watch panel
The system SHALL query only active manufacturer part numbers from a versioned watch panel. Each panel member MUST be labeled `core` or `exploratory` and MUST reference a panel version.

#### Scenario: Core and exploratory members are collected
- **WHEN** panel version `2026-Q3` contains 300 active core members and 50 active exploratory members
- **THEN** the collector queries exactly those 350 configured manufacturer part numbers
- **THEN** only core members contribute to the official category index

#### Scenario: Unconfigured catalog parts are excluded
- **WHEN** the Future API exposes parts outside the active watch panel
- **THEN** the collector SHALL NOT enumerate or persist those parts

### Requirement: Future requests use bounded batches and explicit failures
The system SHALL submit at most 300 manufacturer part numbers in one Future batch request. It SHALL classify authentication and licensing responses as terminal source failures and rate-limit or server responses as bounded retryable failures.

#### Scenario: More than 300 configured parts
- **WHEN** 650 active parts require collection
- **THEN** the system sends three batches containing at most 300 parts each

#### Scenario: License rejection
- **WHEN** Future responds with HTTP 401, 402, 403, or 406
- **THEN** the system stops Future collection without retrying that failure
- **THEN** the run status records a redacted terminal error

#### Scenario: Transient failure
- **WHEN** Future responds with HTTP 429 or a 5xx status
- **THEN** the system retries no more than three total attempts using bounded backoff

### Requirement: Source rights are machine-readable
Every persistent source SHALL define `persist_allowed`, `cloud_share_allowed`, `raw_retention_days`, `attribution_required`, `terms_reviewed_at`, and `terms_url`. The issued API agreement SHALL remain the controlling authority when it imposes stricter conditions.

#### Scenario: Persistence is disabled by an issued agreement
- **WHEN** the active Future source policy has `persist_allowed = false`
- **THEN** collection stops before any Future response is written to a persistent sink

### Requirement: User-owned CSV ingestion is offline and auditable
The system SHALL import authorized CSV observations with source attribution and a file hash. It MUST reject negative quantities, naive timestamps, invalid currency codes, and conflicting duplicate fields.

#### Scenario: Repeated authorized CSV import
- **WHEN** an operator imports the same valid CSV twice
- **THEN** the second import creates no duplicate observation or price break
