# Component Supply Radar Implementation Plan

> **Historical and superseded:** Native Windows distribution is defined by `../specs/2026-07-12-windows-distribution-design.md`, and automated ingestion is Future Electronics only. Do not implement the macOS or Mouser steps retained below as historical planning context.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested macOS-local Python collector that stores permitted component supply history in DuckDB, shares permitted normalized tables through MotherDuck, creates Parquet backups, and emits HTML/CSV supply-tightness reports.

**Architecture:** A typed provider boundary normalizes Future Electronics API and user-owned CSV data while a policy gate prevents Mouser responses from reaching persistent sinks. A local DuckDB file is the writable authority; reports, weekly Parquet backups, and a one-way MotherDuck publisher are downstream consumers.

**Tech Stack:** Python 3.12, uv, DuckDB/MotherDuck, HTTPX, Typer, Jinja2, python-dotenv, pytest, pytest-httpx, Ruff, mypy.

## Global Constraints

- Track 300–1,000 configured MPNs; never enumerate or bulk-download a supplier catalog.
- Store timestamps in UTC and render user-facing times in `Asia/Taipei`.
- Never persist Mouser API responses unless the source policy is explicitly changed after written authorization.
- Never commit API keys, real supplier data, DuckDB files, Parquet backups, logs, or real watchlists.
- Local operation must work without `MOTHERDUCK_TOKEN`.
- Use transparent 0–100 rules; do not generate stock buy/sell advice.
- Production API smoke tests are opt-in; the default suite is fully offline.

---

## File Map

- `pyproject.toml`: package metadata, dependencies, CLI entry point, lint and test configuration.
- `src/component_supply_radar/models.py`: normalized immutable domain records.
- `src/component_supply_radar/config.py`: environment and path configuration.
- `src/component_supply_radar/policy.py`: persistent-sink authorization checks.
- `src/component_supply_radar/storage.py`: schema migrations and DuckDB repository.
- `src/component_supply_radar/providers/csv_import.py`: user-owned CSV normalization.
- `src/component_supply_radar/providers/future.py`: licensed Future API client.
- `src/component_supply_radar/providers/mouser.py`: non-persistent live Mouser client.
- `src/component_supply_radar/pipeline.py`: collection orchestration, retries, and run audit.
- `src/component_supply_radar/signals.py`: deterministic supply-tightness calculations.
- `src/component_supply_radar/reporting.py`: HTML and CSV output.
- `src/component_supply_radar/sync.py`: one-way MotherDuck publication.
- `src/component_supply_radar/backup.py`: partitioned Parquet backup and retention.
- `src/component_supply_radar/cli.py`: Typer commands and daily workflow.
- `scripts/install_launchd.sh`, `scripts/uninstall_launchd.sh`: macOS scheduling.
- `README.md`: setup, source policy, operation, sharing, storage sizing, and references.

### Task 1: Package, configuration, domain records, and policy gate

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `src/component_supply_radar/__init__.py`
- Create: `src/component_supply_radar/models.py`
- Create: `src/component_supply_radar/config.py`
- Create: `src/component_supply_radar/policy.py`
- Test: `tests/test_config_policy.py`

**Interfaces:**
- Produces: `Settings.from_env() -> Settings`, `SourcePolicy`, `Observation`, `PriceBreak`, `assert_persistence_allowed(policy)`.

- [ ] **Step 1: Write the failing configuration and policy tests**

```python
from pathlib import Path
import pytest
from component_supply_radar.config import Settings
from component_supply_radar.models import SourcePolicy
from component_supply_radar.policy import PersistenceForbidden, assert_persistence_allowed

def test_defaults_are_local_and_motherduck_optional(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MOTHERDUCK_TOKEN", raising=False)
    settings = Settings.from_env()
    assert settings.database_path == tmp_path / "data" / "radar.duckdb"
    assert settings.timezone == "Asia/Taipei"
    assert settings.motherduck_token is None

def test_mouser_policy_cannot_reach_persistent_sink() -> None:
    policy = SourcePolicy("mouser", "forbidden", 0, False)
    with pytest.raises(PersistenceForbidden):
        assert_persistence_allowed(policy)
```

- [ ] **Step 2: Run `uv run pytest tests/test_config_policy.py -q` and confirm import failure**

Expected: collection fails because `component_supply_radar` does not exist.

- [ ] **Step 3: Implement exact records and policy behavior**

```python
@dataclass(frozen=True, slots=True)
class SourcePolicy:
    source_id: str
    storage_policy: Literal["forbidden", "licensed", "user_owned"]
    raw_retention_days: int
    cloud_share_allowed: bool

@dataclass(frozen=True, slots=True)
class PriceBreak:
    quantity_from: int
    quantity_to: int | None
    unit_price: Decimal
    currency: str

@dataclass(frozen=True, slots=True)
class Observation:
    source_id: str
    mpn: str
    manufacturer: str
    observed_at_utc: datetime
    quantity_available: int | None
    quantity_factory: int | None
    quantity_on_order: int | None
    minimum_order_quantity: int | None
    order_multiple: int | None
    lead_time_days: int | None
    currency: str | None
    lifecycle: str | None
    region: str | None
    price_breaks: tuple[PriceBreak, ...]
    ingest_hash: str

class PersistenceForbidden(RuntimeError):
    pass

def assert_persistence_allowed(policy: SourcePolicy) -> None:
    if policy.storage_policy == "forbidden":
        raise PersistenceForbidden(f"{policy.source_id} data may not be persisted")
```

- [ ] **Step 4: Run `uv run pytest tests/test_config_policy.py -q` and confirm two passes**
- [ ] **Step 5: Commit with `git commit -m 'feat: add configuration and source policy'`**

### Task 2: Versioned DuckDB schema and idempotent repository

**Files:**
- Create: `src/component_supply_radar/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Consumes: `Observation`, `SourcePolicy`.
- Produces: `RadarRepository.initialize()`, `save_observations(policy, observations)`, `record_run(...)`, `query_observations()`.

- [ ] **Step 1: Write a failing test that saves one observation twice**

```python
def test_save_observation_is_idempotent(tmp_path: Path, sample_observation: Observation) -> None:
    repo = RadarRepository(tmp_path / "radar.duckdb")
    repo.initialize()
    policy = SourcePolicy("csv", "user_owned", 30, True)
    repo.save_observations(policy, [sample_observation])
    repo.save_observations(policy, [sample_observation])
    assert repo.count("observations") == 1
    assert repo.count("price_breaks") == len(sample_observation.price_breaks)
```

- [ ] **Step 2: Run the test and confirm `RadarRepository` is missing**
- [ ] **Step 3: Implement migration version 1 and transactional inserts**

```sql
CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at_utc TIMESTAMPTZ NOT NULL);
CREATE TABLE IF NOT EXISTS sources(source_id VARCHAR PRIMARY KEY, display_name VARCHAR NOT NULL, storage_policy VARCHAR NOT NULL, raw_retention_days INTEGER NOT NULL, cloud_share_allowed BOOLEAN NOT NULL);
CREATE TABLE IF NOT EXISTS parts(mpn VARCHAR NOT NULL, manufacturer VARCHAR NOT NULL, category VARCHAR, ticker VARCHAR, active BOOLEAN NOT NULL DEFAULT TRUE, notes VARCHAR, PRIMARY KEY(mpn, manufacturer));
CREATE TABLE IF NOT EXISTS collection_runs(run_id UUID PRIMARY KEY, source_id VARCHAR NOT NULL, started_at_utc TIMESTAMPTZ NOT NULL, completed_at_utc TIMESTAMPTZ, status VARCHAR NOT NULL, request_count INTEGER NOT NULL, success_count INTEGER NOT NULL, failure_count INTEGER NOT NULL, error_summary VARCHAR);
CREATE TABLE IF NOT EXISTS observations(observation_id UUID PRIMARY KEY, source_id VARCHAR NOT NULL, mpn VARCHAR NOT NULL, manufacturer VARCHAR NOT NULL, observed_at_utc TIMESTAMPTZ NOT NULL, quantity_available BIGINT, quantity_factory BIGINT, quantity_on_order BIGINT, minimum_order_quantity BIGINT, order_multiple BIGINT, lead_time_days INTEGER, currency VARCHAR, lifecycle VARCHAR, region VARCHAR, ingest_hash VARCHAR NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS price_breaks(observation_id UUID NOT NULL, quantity_from BIGINT NOT NULL, quantity_to BIGINT, unit_price DECIMAL(18,6) NOT NULL, currency VARCHAR NOT NULL, PRIMARY KEY(observation_id, quantity_from));
CREATE TABLE IF NOT EXISTS signals(source_id VARCHAR NOT NULL, mpn VARCHAR NOT NULL, calculated_for DATE NOT NULL, inventory_change_7d DOUBLE, inventory_change_30d DOUBLE, price_change_7d DOUBLE, price_change_30d DOUBLE, lead_time_change_30d INTEGER, stockout_ratio DOUBLE, tightness_score DOUBLE, reasons VARCHAR[], data_sufficient BOOLEAN NOT NULL, PRIMARY KEY(source_id, mpn, calculated_for));
```

Insert observations with `INSERT ... ON CONFLICT(ingest_hash) DO NOTHING`, resolve the stable `observation_id` from `uuid5(NAMESPACE_URL, ingest_hash)`, and insert price breaks in the same transaction.

- [ ] **Step 4: Add tests for policy rejection and transaction rollback, then run the whole storage test file**
- [ ] **Step 5: Commit with `git commit -m 'feat: add DuckDB repository'`**

### Task 3: Watchlist and user-owned CSV ingestion

**Files:**
- Create: `config/watchlist.example.csv`
- Create: `examples/supplier-observations.csv`
- Create: `src/component_supply_radar/providers/__init__.py`
- Create: `src/component_supply_radar/providers/csv_import.py`
- Test: `tests/test_csv_import.py`

**Interfaces:**
- Produces: `load_watchlist(path) -> tuple[Part, ...]`, `read_observations_csv(path, source_id) -> tuple[Observation, ...]`.

- [ ] **Step 1: Write failing tests for valid normalization, duplicate price rows, and invalid timezone/quantity**

```python
def test_csv_rows_form_one_observation_with_two_price_breaks(tmp_path: Path) -> None:
    path = write_csv(tmp_path, [
        row(price_quantity="1", unit_price="1.20"),
        row(price_quantity="100", unit_price="0.80"),
    ])
    observations = read_observations_csv(path, "owned_csv")
    assert len(observations) == 1
    assert [p.quantity_from for p in observations[0].price_breaks] == [1, 100]
    assert observations[0].observed_at_utc.tzinfo is not None
```

- [ ] **Step 2: Run the test and confirm the CSV importer is missing**
- [ ] **Step 3: Parse the documented CSV columns and hash canonical JSON with SHA-256**

Required columns are `mpn`, `manufacturer`, `observed_at_utc`, `quantity_available`, `lead_time_days`, `currency`, `price_quantity`, and `unit_price`. Optional columns are `quantity_factory`, `quantity_on_order`, `minimum_order_quantity`, `order_multiple`, `lifecycle`, and `region`. Reject negative quantities, naive timestamps, invalid three-letter currencies, and conflicting repeated observation fields.

- [ ] **Step 4: Run importer tests and `ruff check` for the new files**
- [ ] **Step 5: Commit with `git commit -m 'feat: import user-owned supplier CSV'`**

### Task 4: Future licensed API and non-persistent Mouser live lookup

**Files:**
- Create: `src/component_supply_radar/providers/future.py`
- Create: `src/component_supply_radar/providers/mouser.py`
- Create: `tests/fixtures/future_batch.json`
- Create: `tests/fixtures/mouser_search.json`
- Test: `tests/test_future_provider.py`
- Test: `tests/test_mouser_provider.py`

**Interfaces:**
- Produces: `FutureClient.collect(mpns, observed_at_utc) -> tuple[Observation, ...]` and `MouserLiveClient.lookup(mpn) -> tuple[LiveQuote, ...]`.
- Constraint: `LiveQuote` is deliberately incompatible with `RadarRepository.save_observations`.

- [ ] **Step 1: Write HTTPX fixture tests for Future batch normalization**

```python
def test_future_batch_normalizes_inventory_lead_time_and_prices(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(json=fixture("future_batch.json"))
    client = FutureClient("secret", base_url="https://api.future.test")
    observations = client.collect(["BAT54STA"], NOW)
    assert observations[0].quantity_available == 5000
    assert observations[0].lead_time_days == 70
    assert observations[0].price_breaks[0].unit_price == Decimal("0.218")
    assert "secret" not in repr(client)
```

- [ ] **Step 2: Run the Future test and confirm failure before implementation**
- [ ] **Step 3: Implement batches of at most 300 MPNs, explicit timeouts, and status classification**

Send `POST /api/v1/pim-future/batch/lookup` with `x-orbweaver-licensekey`, normalize weeks to seven days, use UTC timestamps supplied by the caller, and raise `ProviderAuthError` for 401/402/403/406, `ProviderRateLimitError` for 429, and `ProviderTransientError` for 5xx.

- [ ] **Step 4: Write and pass Mouser tests proving live output has no persistence conversion or logging**

```python
def test_mouser_live_quote_cannot_be_saved(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(json=fixture("mouser_search.json"))
    quotes = MouserLiveClient("secret").lookup("BAT54STA")
    repo = RadarRepository(tmp_path / "radar.duckdb")
    repo.initialize()
    with pytest.raises(TypeError):
        repo.save_observations(MOUSER_POLICY, quotes)  # type: ignore[arg-type]
```

- [ ] **Step 5: Commit with `git commit -m 'feat: add supplier API clients'`**

### Task 5: Collection pipeline, retries, audit, and daily workflow

**Files:**
- Create: `src/component_supply_radar/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Produces: `Collector.run(provider, policy, mpns, now) -> RunResult` and `run_daily(settings) -> DailyResult`.

- [ ] **Step 1: Write failing tests for partial batches, 429 retry, and auth stop**

```python
def test_transient_failure_retries_and_saves_once(fake_provider: FakeProvider, repo: RadarRepository) -> None:
    fake_provider.failures = [ProviderRateLimitError("slow down")]
    result = Collector(repo, sleep=lambda _: None).run(fake_provider, LICENSED, ["A", "B"], NOW)
    assert result.status == "success"
    assert fake_provider.calls == 2
    assert repo.count("observations") == 2

def test_auth_failure_is_not_retried(fake_provider: FakeProvider, repo: RadarRepository) -> None:
    fake_provider.failures = [ProviderAuthError("invalid license")]
    result = Collector(repo, sleep=lambda _: None).run(fake_provider, LICENSED, ["A"], NOW)
    assert result.status == "failed"
    assert fake_provider.calls == 1
```

- [ ] **Step 2: Run and observe the missing pipeline failure**
- [ ] **Step 3: Implement at most three attempts with 1, 2, and 4 second delays and redacted audit messages**
- [ ] **Step 4: Add a forbidden-policy test that fails before the provider receives a network call**
- [ ] **Step 5: Commit with `git commit -m 'feat: orchestrate audited collection runs'`**

### Task 6: Transparent tightness signals

**Files:**
- Create: `src/component_supply_radar/signals.py`
- Test: `tests/test_signals.py`

**Interfaces:**
- Produces: `calculate_signal(current, seven_day, thirty_day, stockout_ratio) -> Signal` and `refresh_signals(repo, for_date)`.

- [ ] **Step 1: Write failing boundary and insufficient-data tests**

```python
def test_maximum_component_scores_are_capped_at_100() -> None:
    signal = calculate_signal(
        current=MetricPoint(stock=0, price=Decimal("1.20"), lead_days=112),
        seven_day=None,
        thirty_day=MetricPoint(stock=100, price=Decimal("1.00"), lead_days=56),
        stockout_ratio=1.0,
    )
    assert signal.tightness_score == 100
    assert signal.data_sufficient is True

def test_missing_comparison_is_not_zero_pressure() -> None:
    signal = calculate_signal(MetricPoint(10, Decimal("1"), 14), None, None, 0)
    assert signal.tightness_score is None
    assert signal.data_sufficient is False
```

- [ ] **Step 2: Run and observe missing signal types**
- [ ] **Step 3: Implement linear capped components: inventory 35, lead time 25, price 25, breadth 15**

Inventory score is `clamp(-inventory_change_30d / 0.50, 0, 1) * 35`; lead score is `clamp(lead_delta_days / 56, 0, 1) * 25`; price score is `clamp(price_change_30d / 0.20, 0, 1) * 25`; breadth is `clamp(stockout_ratio, 0, 1) * 15`.

- [ ] **Step 4: Add repository integration coverage for nearest observations at or before 7 and 30 days**
- [ ] **Step 5: Commit with `git commit -m 'feat: calculate supply tightness signals'`**

### Task 7: Reports, MotherDuck publication, and Parquet backup

**Files:**
- Create: `src/component_supply_radar/reporting.py`
- Create: `src/component_supply_radar/templates/report.html.j2`
- Create: `src/component_supply_radar/sync.py`
- Create: `src/component_supply_radar/backup.py`
- Test: `tests/test_reporting_sync_backup.py`

**Interfaces:**
- Produces: `write_report(repo, output_dir, timezone)`, `publish_to_motherduck(repo, token, database_name)`, `create_backup(repo, backup_root, keep=12)`.

- [ ] **Step 1: Write failing report tests for insufficient data and source attribution**

```python
def test_report_labels_insufficient_data_and_never_gives_trade_advice(seeded_repo: RadarRepository, tmp_path: Path) -> None:
    html_path, csv_path = write_report(seeded_repo, tmp_path, "Asia/Taipei")
    html = html_path.read_text()
    assert "資料不足" in html
    assert "資料來源" in html
    assert "買進" not in html and "賣出" not in html
    assert csv_path.exists()
```

- [ ] **Step 2: Run and observe missing report implementation**
- [ ] **Step 3: Implement escaped Jinja2 HTML and UTF-8-SIG CSV sorted by score descending**
- [ ] **Step 4: Test one-way publication with a temporary DuckDB target and reject `cloud_share_allowed = false` sources**
- [ ] **Step 5: Test backup manifests, Hive-style year/month partitions, and deletion beyond 12 snapshots**
- [ ] **Step 6: Commit with `git commit -m 'feat: publish reports and backups'`**

### Task 8: CLI, macOS scheduler, README, and end-to-end verification

**Files:**
- Create: `src/component_supply_radar/cli.py`
- Create: `scripts/install_launchd.sh`
- Create: `scripts/uninstall_launchd.sh`
- Create: `README.md`
- Test: `tests/test_cli_e2e.py`

**Interfaces:**
- Produces console command `component-supply-radar` with `init-db`, `import-csv`, `collect-future`, `mouser-live`, `analyze`, `report`, `sync`, `backup`, and `run-daily`.

- [ ] **Step 1: Write a failing CLI end-to-end test**

```python
def test_demo_csv_to_html_report(tmp_path: Path) -> None:
    db = tmp_path / "radar.duckdb"
    result = runner.invoke(app, ["--database", str(db), "import-csv", "examples/supplier-observations.csv"])
    assert result.exit_code == 0
    assert "匯入" in result.stdout
    assert runner.invoke(app, ["--database", str(db), "analyze"]).exit_code == 0
    report = runner.invoke(app, ["--database", str(db), "report", "--output", str(tmp_path / "reports")])
    assert report.exit_code == 0
    assert (tmp_path / "reports" / "latest.html").exists()
```

- [ ] **Step 2: Run and observe the missing CLI failure**
- [ ] **Step 3: Implement commands with Chinese help text and nonzero exits for missing credentials or invalid input**
- [ ] **Step 4: Add launchd scripts that resolve the repository absolute path, run at 07:30 Asia/Taipei, and keep logs under ignored `data/logs/`**
- [ ] **Step 5: Write README sections for installation, API applications, source policy, storage sizing, commands, MotherDuck sharing, scheduling, backups, troubleshooting, reference sites, and investment disclaimer**
- [ ] **Step 6: Run fresh verification**

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run component-supply-radar --help
uv run component-supply-radar --database work/demo.duckdb import-csv examples/supplier-observations.csv
uv run component-supply-radar --database work/demo.duckdb analyze
uv run component-supply-radar --database work/demo.duckdb report --output work/report
git diff --check
git status --short
```

Expected: all tests, lint, formatting, type checks, CLI commands, and demo flow exit zero; `work/report/latest.html` and `latest.csv` exist; no secret or generated data is staged.

- [ ] **Step 7: Commit with `git commit -m 'feat: complete component supply radar MVP'`**
- [ ] **Step 8: Push the implementation branch and integrate it into `main` only after the finishing-branch checklist passes**
