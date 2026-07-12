## ADDED Requirements

### Requirement: Part pressure uses transparent bounded components
The system SHALL calculate part-level inventory, lead-time, price, and stockout-breadth components with a combined range of 0 through 100. It MUST mark the result as insufficient when fewer than two comparable historical observations exist.

#### Scenario: Maximum pressure components
- **WHEN** 30-day inventory falls at least 50 percent, lead time rises at least 56 days, comparable price rises at least 20 percent, and stockout breadth equals 1
- **THEN** the part pressure score equals 100

#### Scenario: No historical comparator
- **WHEN** a part has only one valid observation
- **THEN** its pressure score is null
- **THEN** its data status is `insufficient`

### Requirement: Official category pressure uses core-panel robust aggregation
The system SHALL calculate official category intensity as the median of valid core-member part scores. It SHALL calculate category breadth as the proportion of valid core members above the configured pressure threshold. Exploratory members MUST NOT affect the official category result.

#### Scenario: Extreme part does not dominate category intensity
- **WHEN** five valid core part scores are 10, 20, 30, 40, and 100
- **THEN** category intensity equals 30

#### Scenario: Exploratory pressure is excluded
- **WHEN** all exploratory members score 100 and all valid core members score 20
- **THEN** the official category intensity equals 20

### Requirement: Category output includes coverage
Every category result SHALL report valid core part count, configured core part count, distinct contributing source count, and data sufficiency. It MUST NOT publish a conclusive category state below the configured minimum coverage.

#### Scenario: Coverage is below minimum
- **WHEN** fewer valid core members exist than the configured minimum
- **THEN** the category state is `unknown`
- **THEN** the output includes the valid and configured counts

### Requirement: Alerts use a multi-stage state machine
The system SHALL produce `normal`, `watch`, `confirmed`, `recovering`, or `unknown`. A single intensity of at least 60 SHALL produce `watch`; `confirmed` SHALL require at least three intensities of at least 60 in the latest seven calendar days and a latest category intensity of at least 70. A previously confirmed or recovering category SHALL remain `recovering` while its sufficient intensity is from 40 through 59 and SHALL return to `normal` below 40.

#### Scenario: Single spike
- **WHEN** category intensity first reaches 65 with sufficient coverage
- **THEN** the category state becomes `watch`

#### Scenario: Persistent pressure
- **WHEN** at least three observations in seven days qualify for `watch` and the latest category intensity is 75
- **THEN** the category state becomes `confirmed`

#### Scenario: Failed collection after confirmed pressure
- **WHEN** the previous state is `confirmed` and current coverage is insufficient because collection failed
- **THEN** the current state is `unknown`
- **THEN** the system SHALL NOT label the category recovered
