# GitHub Repo Fine-Tune Dataset Design

Date: 2026-06-24
Status: Approved design, pending user review before implementation

## Goal

Build a reusable dataset pipeline that collects all accessible GitHub repositories for the user, including public and private repositories, and converts repository artifacts into mixed fine-tuning datasets for:

- instruction-style assistant tuning
- completion-style code tuning

The pipeline must run its working set from `R:` so large raw data, caches, and generated outputs do not live inside the BossForgeOS repo.

## Scope

Version 1 includes:

- repository source files
- selected documentation files
- commit messages and diffs
- issues and issue comments
- pull request bodies, review comments, and merged diffs
- mixed dataset generation for instruction and completion outputs
- train and validation split generation
- OpenAI-oriented manifest output
- Hugging Face-oriented manifest output
- provenance, redaction, exclusion, and reporting

Version 1 does not include:

- direct Copilot or VS Code chat export ingestion
- model training execution
- synthetic data generation beyond source-grounded transformations
- broad filesystem scraping outside explicitly collected GitHub data

## Primary Outcomes

The pipeline must produce:

1. local JSONL datasets for instruction tuning
2. local JSONL datasets for completion tuning
3. train and validation splits for both dataset families
4. manifests and config outputs for OpenAI-style and Hugging Face-style downstream fine-tuning
5. reports describing what was collected, filtered, redacted, and emitted

## Storage Layout

The pipeline workspace lives at:

`R:\AI\repo-finetune`

Recommended layout:

- `R:\AI\repo-finetune\config\`
- `R:\AI\repo-finetune\cache\`
- `R:\AI\repo-finetune\raw\`
- `R:\AI\repo-finetune\normalized\`
- `R:\AI\repo-finetune\output\instruction\`
- `R:\AI\repo-finetune\output\completion\`
- `R:\AI\repo-finetune\reports\`
- `R:\AI\repo-finetune\manifests\`

Key files:

- `R:\AI\repo-finetune\config\repos.json`
- `R:\AI\repo-finetune\config\filters.json`
- `R:\AI\repo-finetune\normalized\records.jsonl`
- `R:\AI\repo-finetune\output\instruction\all.jsonl`
- `R:\AI\repo-finetune\output\instruction\train.jsonl`
- `R:\AI\repo-finetune\output\instruction\val.jsonl`
- `R:\AI\repo-finetune\output\completion\all.jsonl`
- `R:\AI\repo-finetune\output\completion\train.jsonl`
- `R:\AI\repo-finetune\output\completion\val.jsonl`
- `R:\AI\repo-finetune\manifests\openai-chat.json`
- `R:\AI\repo-finetune\manifests\huggingface.json`

## Design Approach

The approved design uses a metadata-first pipeline.

The pipeline should prefer GitHub API and GitHub-app-backed collection of repository metadata and discussions, then normalize all fetched artifacts into a common internal representation. If a repository is too large or API retrieval is incomplete for a needed artifact, the design allows a targeted fallback to local clone-based extraction for that repository only.

This approach is preferred because it:

- keeps control over privacy filtering and provenance
- avoids cloning every repository by default
- makes issues, pull requests, comments, and diffs first-class sources
- keeps reruns incremental and resumable

## Data Sources

For each accessible repository, the pipeline should attempt to collect:

- repository metadata
- default branch and selected branch context
- source files
- selected documentation files such as `README`, `docs/`, architecture notes, guides, and design docs
- commit metadata
- commit messages
- commit diffs or bounded diff windows
- issues
- issue comments
- pull requests
- pull request bodies
- pull request review comments
- merged diff content or bounded patch windows

Each record must carry source metadata including:

- repository name
- repository visibility
- source artifact type
- path or discussion identifier
- commit SHA or PR/issue identifier where applicable
- author metadata when available
- timestamp when available

## Internal Record Model

All collected artifacts should normalize into a common JSONL-oriented schema. Each normalized record should include fields such as:

- `record_id`
- `repo`
- `repo_visibility`
- `source_type`
- `path`
- `sha`
- `issue_number`
- `pr_number`
- `comment_id`
- `author`
- `timestamp`
- `language`
- `content`
- `diff`
- `metadata`

The exact shape may vary by artifact type, but every normalized record must support provenance and downstream filtering.

## Filtering Rules

The pipeline must exclude or quarantine low-signal and risky inputs before dataset generation.

Required exclusions:

- binaries
- vendored dependencies
- generated build output
- lockfiles unless explicitly allowed later
- archive files
- media blobs
- giant minified assets
- cached runtime artifacts
- obviously duplicated mirrors

Required safety filtering:

- secret scanning and redaction
- token and credential pattern removal
- optional private key and certificate quarantine
- large blob rejection
- suspicious content quarantine report instead of silent discard

Required quality filtering:

- duplicate collapse
- near-duplicate suppression where practical
- bounded file and diff sizes
- configurable include and exclude globs

## Dataset Families

### Instruction Dataset

The instruction dataset should convert repository artifacts into assistant-style prompt and response examples. Example categories include:

- issue to implementation intent
- issue to resolution summary
- pull request diff to review summary
- review comment to patch rationale
- commit diff to concise explanation
- documentation to question and answer examples
- bugfix before and after context to debugging explanation

Instruction examples should preserve provenance and include a stable mapping back to the originating repository artifact.

### Completion Dataset

The completion dataset should emphasize code continuation and implementation examples. Example categories include:

- code prefix to next chunk
- function signature or stub to implementation
- before window to after window from commit diffs
- bugfix localized context to corrected completion

Completion examples should use bounded windows to avoid oversized samples and should preserve file path and repository provenance.

## Split Strategy

The pipeline must write:

- full dataset files
- train split files
- validation split files

The split logic should avoid exact duplicate leakage across train and validation. Where practical, related examples from the same atomic artifact should remain in the same split to reduce evaluation contamination.

## Packaging Outputs

### OpenAI-Oriented Outputs

The pipeline should emit OpenAI-style chat-oriented dataset files and a manifest describing:

- file locations
- example counts
- expected schema
- recommended usage notes

### Hugging Face-Oriented Outputs

The pipeline should emit Hugging Face-friendly JSONL or JSON plus a manifest describing:

- dataset file locations
- split definitions
- schema details
- optional tokenizer or training-notes placeholders for later use

## Pipeline Stages

### 1. Collect

Fetch all accessible repository artifacts through GitHub-backed collection.

Responsibilities:

- enumerate repositories
- capture visibility and metadata
- fetch code and docs
- fetch commits and diffs
- fetch issues, PRs, and comments
- checkpoint progress per repository

### 2. Normalize

Convert heterogeneous source artifacts into the common internal schema.

Responsibilities:

- produce `records.jsonl`
- attach provenance
- preserve source typing
- normalize timestamps and identifiers

### 3. Filter

Apply exclusion, redaction, dedupe, and quality rules before example generation.

Responsibilities:

- drop blocked artifacts
- redact risky content
- quarantine suspicious records
- produce filtering summaries

### 4. Generate Examples

Transform normalized records into instruction and completion examples.

Responsibilities:

- classify source artifacts into candidate example families
- render prompt/response examples
- render prefix/completion examples
- enforce example size and quality constraints

### 5. Split And Package

Write dataset outputs and manifests.

Responsibilities:

- generate full datasets
- create train and validation splits
- emit OpenAI and Hugging Face manifests

### 6. Report

Produce operator-readable summaries.

Required reporting:

- counts by repository
- counts by visibility
- counts by source type
- counts by example type
- exclusions and redactions
- quarantine counts

## Safety And Recovery Model

The pipeline must be resumable and conservative.

Required behavior:

- per-repository checkpoints
- retry and rate-limit handling for GitHub fetches
- failure isolation so one bad repository does not abort the whole run
- quarantine reports for dropped or suspicious data
- provenance on every emitted example
- public and private visibility tagging on every normalized and generated record

This visibility tagging supports future datasets such as:

- mixed public and private
- public-only
- private-only

## Verification Requirements

Before a run is considered successful, the pipeline should verify:

- every output example has provenance
- instruction examples contain non-empty prompt and response structures
- completion examples contain valid prefix and completion structures
- split files do not contain exact duplicate leakage across train and validation
- secret scans pass or produce explicit reports
- manifests reference files that exist
- report totals reconcile with produced outputs

## Repo Integration

Implementation should live in BossForgeOS as code and documentation, but heavy runtime data should remain on `R:`.

The repository should contain:

- pipeline source code
- configuration templates
- usage documentation
- manifests or schema definitions that belong under version control

The repository should not contain:

- raw harvested GitHub payloads
- large normalized caches
- generated dataset outputs

## Suggested Implementation Units

The eventual implementation should separate responsibilities into small focused modules:

- repository enumeration and fetch orchestration
- normalized record writing
- filtering and redaction
- instruction example generation
- completion example generation
- split logic
- manifest generation
- reporting

This keeps each unit independently testable and easier to evolve.

## Open Questions Deferred To Implementation Planning

These decisions are intentionally deferred to the implementation plan rather than left ambiguous:

- exact GitHub connector or API path used for collection
- exact normalized schema field names where multiple reasonable names exist
- exact prompt templates for instruction examples
- exact windowing heuristics for completion examples
- exact secret-scanning library or regex strategy
- exact manifest schema details for each target ecosystem

The implementation plan must pick concrete answers for these items.

## Success Criteria

The design is successful when a future implementation can:

1. collect all accessible public and private GitHub repositories
2. generate mixed instruction and completion fine-tuning datasets
3. write all heavy working data to `R:\AI\repo-finetune`
4. package train and validation outputs for OpenAI and Hugging Face downstream use
5. provide enough provenance and reporting to audit every emitted example
