## ADDED Requirements

### Requirement: Raw and canonical categories are both retained
The system SHALL preserve the Future-provided category value and SHALL map each tracked part to one versioned canonical category. Category analysis MUST use the canonical value while reports MUST expose both values for audit.

#### Scenario: Supplier category mapping
- **WHEN** Future returns a supplier category mapped to canonical category `power-semiconductor`
- **THEN** both the original category and `power-semiconductor` are stored

### Requirement: Direct manufacturer exposure is evidence-backed
The system SHALL create direct exposure only from a tracked part's manufacturer identity and an explicit reviewed issuer mapping. Direct exposure MUST retain mapping version, reviewer, review time, and evidence reference.

#### Scenario: Reviewed manufacturer mapping
- **WHEN** a tracked part manufacturer has an active reviewed issuer mapping
- **THEN** the category report lists the mapped issuer under direct exposure

#### Scenario: Missing issuer mapping
- **WHEN** no reviewed issuer mapping exists
- **THEN** the system displays no direct ticker for that manufacturer

### Requirement: Thematic exposure is separate and labeled as a research assumption
The system SHALL store upstream, downstream, and alternative-supplier thematic exposure separately from direct exposure. It MUST label thematic relationships as manually curated research assumptions and MUST NOT combine them into the objective supply-pressure score.

#### Scenario: Downstream company is curated
- **WHEN** a researcher links a downstream company to canonical category `memory`
- **THEN** the company appears only in thematic exposure
- **THEN** the category pressure score remains unchanged

### Requirement: Exposure output does not provide trade instructions
The system SHALL present exposure context and provenance without producing buy, sell, position-size, or return-prediction instructions.

#### Scenario: Confirmed category pressure
- **WHEN** a category state is `confirmed`
- **THEN** the report lists relevant direct and thematic exposure with provenance
- **THEN** the report contains no trade instruction
