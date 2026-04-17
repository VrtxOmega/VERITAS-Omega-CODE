# VERITAS Ω-CODE v2.0
### Deterministic Software Verification Layer

**Status:** SEALED  
**Version:** 2.0.0  
**Sealed:** `SHA256:637e324085b94b26493234afa756236f3dc104f377693aaa141a1faca686a90a`  
**Lineage:** Ω-CODE v1.0 → Ω Build v1.0.0 → Ω-CODE v2.0  
**Feeds into:** omega-brain-mcp · AEGIS/AEGIS-Rewrite · Gravity-Omega · S.E.A.L. Ledger

---

## Core Principle

> "If it cannot be expressed as typed, declared, constraint-bound assertions with artifact evidence, it cannot be evaluated."

Ω-CODE v2.0 aligns the code-domain verification layer with the omega-brain-mcp 10-gate pipeline architecture and the VERITAS Ω Build v1.0.0 specification, while preserving the deterministic enforcement innovations from Ω-CODE v1.0.

---

## 1. Claim Object

All pipeline input is a **BuildClaim** — a structured object, not a string grammar. Every field must be present and non-null.

```
BuildClaim := {
  id:            ClaimID,
  project:       String,
  version:       SemVer,
  commit:        Hash,
  P:             Set[BuildPrimitive],     // what we measure
  O:             Set[Operator],           // how we combine measurements
  R:             Set[BuildRegime],        // under what deployment conditions
  B:             Set[Boundary],           // what constraints must hold
  L:             Set[LossModel],          // what failure costs
  E:             Set[EvidenceItem],       // proof it holds
  cost:          CostVector,
  cost_bounds:   CostBounds,
  attack_suite:  AttackSuite,
  dependencies:  DependencyManifest,
  security:      SecurityManifest,
  created_at:    Timestamp
}

ClaimID := SHA256(canonical(
  project + version + commit + P + O + R + B + L + PolicyHash
))
```

### 1.0a Set Canonicalization

All set fields (P, O, R, B, L, E) MUST be sorted before hashing:

```
P: sorted by BuildPrimitive.name (lexicographic)
O: sorted by Operator.name (lexicographic)
R: sorted by BuildRegime.name (lexicographic)
B: sorted by Boundary.name (lexicographic)
L: sorted by LossModel.name (lexicographic)
E: sorted by EvidenceItem.id (lexicographic)

DependencyManifest.packages: sorted by PackageRef.name (lexicographic)
SecurityManifest.sast_results: sorted by SASTFinding.location (lexicographic)
AttackSuite: sorted by attack.id (lexicographic)
```

All sets are serialized in canonical JSON (Section 6) after sorting. Two BuildClaims with the same fields in different insertion order MUST produce the same ClaimID.

### 1.1 BuildPrimitive

An observable, measurable property of the software artifact.

```
BuildPrimitive := {
  name:    String,            // e.g. "p99_latency", "coverage", "mutation_kill_rate"
  units:   String,            // e.g. "ms", "ratio", "count"
  domain:  { type: "Interval", low: Number, high: Number }
}
```

Primitives must have unique names. Empty domains are rejected at TYPE gate.

### 1.2 Operator

```
Operator := {
  name:    String,
  arity:   Integer,
  inputs:  List[PrimitiveRef],
  output:  PrimitiveRef
}
```

### 1.3 BuildRegime

Deployment context that determines threshold escalation.

```
BuildRegime := {
  name:       "dev" | "staging" | "prod",
  predicates: List[RegimePredicate]
}

RegimePredicate := {
  variable:  PrimitiveRef,
  operator:  ">=" | "<=" | "==" | "!=" | "<" | ">",
  target:    Number
}
```

Production regime enforces escalated thresholds: K=3, A=0.90, Q=0.80 (per v1.3.1 irreversibility semantics).

### 1.4 Boundary (Constraint)

```
Boundary := {
  name:       String,
  constraint: {
    variable:  PrimitiveRef,
    operator:  ">=" | "<=" | "==" | "!=" | "<" | ">",
    target:    Number
  }
}
```

### 1.5 DependencyManifest

```
DependencyManifest := {
  lockfile_hash:  Hash,
  sbom:           "SPDX" | "CycloneDX",
  packages:       List[PackageRef]
}

PackageRef := {
  name:            String,
  version:         SemVer,
  registry:        String,       // "pypi", "npm", "crates.io"
  integrity_hash:  Hash
}
```

### 1.6 SecurityManifest

```
SecurityManifest := {
  auth_boundaries:    List[String],     // e.g. ["local_stdio", "mcp_protocol"]
  injection_surfaces: List[String],     // e.g. ["mcp_tool_input_json", "api_body"]
  sast_results:       List[SASTFinding],
  secrets_detected:   Boolean,          // zero tolerance — true => VIOLATION
  tls_config:         { min_version: String, mode: String }
}

SASTFinding := {
  tool:      String,
  location:  String,
  severity:  "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
  finding:   String
}
```

---

## 2. Environment Declaration (Preserved from v1.0)

Before any pipeline run, the execution environment MUST be explicitly declared and hashed.

```
ENV_MANIFEST {
  os:              String
  language_ver:    String
  ast_parser:      String
  dependency_lock: Hash           // hash of lockfile (matches DependencyManifest.lockfile_hash)
  gate_config:     Hash           // PolicyHash
  timestamp:       Unix_epoch
}
```

**ENV_HASH** = SHA256(ENV_MANIFEST serialized in canonical JSON key order)

Two runs are considered identical only if their ENV_HASH values match. Different output under the same ENV_HASH is `VIOLATION: NONDETERMINISM` and is logged to the S.E.A.L. ledger.

---

## 3. Verdicts

```
Verdict := PASS | MODEL_BOUND | INCONCLUSIVE | VIOLATION

Precedence: VIOLATION > INCONCLUSIVE > MODEL_BOUND > PASS
```

| Verdict | Meaning | Deploy? |
|---|---|---|
| `PASS` | All gates satisfied. Artifact deployable under declared regime. | Yes |
| `MODEL_BOUND` | Gates pass but resource/coverage/confidence near redline. | With monitoring |
| `INCONCLUSIVE` | Insufficient evidence or solver timeout. Cannot affirm or deny. | No — blocked |
| `VIOLATION` | Constraint failure, vulnerability, or test failure. | No — blocked |

---

## 4. Pipeline

### 4.1 Gate Order (Mandatory)

```
PIPELINE_ORDER := [
  INTAKE,       // Gate 1
  TYPE,         // Gate 2
  DEPENDENCY,   // Gate 3
  EVIDENCE,     // Gate 4
  MATH,         // Gate 5
  COST,         // Gate 6
  INCENTIVE,    // Gate 7
  SECURITY,     // Gate 8
  ADVERSARY,    // Gate 9
  TRACE_SEAL    // Gate 10
]
```

Gates execute in this exact sequence. Parallel or out-of-order execution produces `VIOLATION: PIPELINE_ORDER_MISMATCH`.

### 4.2 Fail-Fast Rule

```
IF Gate N returns VIOLATION:
  → HALT pipeline immediately
  → Final verdict = VIOLATION
  → Remaining gates not executed

IF Gate N returns INCONCLUSIVE:
  → HALT pipeline UNLESS policy declares gate-skip for Gate N
  → If skipped: gate result downgraded to MODEL_BOUND
  → If not skipped: final verdict = INCONCLUSIVE
```

### 4.3 Final Verdict Computation

```
EXECUTED_GATES := all gates that ran before halt (inclusive of halting gate)

final_verdict = max(verdicts over EXECUTED_GATES, by precedence)

Precedence: VIOLATION > INCONCLUSIVE > MODEL_BOUND > PASS
```

Only executed gates participate in the final verdict. Gates that never ran have no verdict — they are absent from the record, not defaulted.

---

## 5. Gate Definitions

### Gate 1 — INTAKE

**Purpose:** Parse, validate, and canonicalize the BuildClaim.

```
INTAKE_GATE(payload):
  1. Parse BuildClaim from source (CI payload, CLI, API)
  2. Validate all required fields present and non-null
  3. Verify commit hash matches HEAD of declared branch
  4. Compute ClaimID from canonical form — verify match
  5. Verify lockfile_hash matches actual lockfile on disk
  6. Validate ENV_MANIFEST is present and hashable

  PASS
  or VIOLATION: INTAKE_MALFORMED
                INTAKE_COMMIT_MISMATCH
                INTAKE_LOCKFILE_DRIFT
```

**Artifact:** `intake_report.json`

---

### Gate 2 — TYPE

**Purpose:** Validate type safety, unit consistency, and symbol resolution across the BuildClaim.

```
TYPE_GATE(claim):
  1. Enforce unique primitive names
  2. Validate non-empty domains for all primitives
  3. Validate operator arity and input/output type references
  4. Check all symbols in constraints reference declared primitives
  5. Validate unit consistency across operators and boundaries
  6. Verify BuildRegime predicates reference declared primitives

  PASS
  or VIOLATION: UNDEFINED_SYMBOL
                UNIT_MISMATCH
                ARITY_ERROR
                EMPTY_DOMAIN
```

**Artifact:** `type_report.json`

**Trust Boundary Detection (preserved from v1.0):**

A `TRUST_BOUNDARY` exists at any point where:
- External input enters the system (user input, network data, file I/O, env vars)
- Privilege level changes (sudo, role escalation, onlyOwner crossing)
- Contract-to-contract or user-to-contract boundary is crossed
- IPC or network boundary exists (socket, pipe, RPC, cross-process memory)
- Deserialization occurs on untrusted data

All trust boundaries are logged in `type_report.json` for downstream SECURITY gate consumption.

---

### Gate 3 — DEPENDENCY

**Purpose:** Supply chain verification. Dependencies are a first-class attack surface.

```
DEPENDENCY_GATE(claim):
  1. Parse SBOM from DependencyManifest
  2. Verify every PackageRef integrity_hash against registry
  3. Scan for known CVEs against vulnerability database:
     - CRITICAL/HIGH CVE with no patch → VIOLATION(CVE_CRITICAL)
     - MEDIUM CVE → MODEL_BOUND(CVE_MEDIUM) if policy allows
     - LOW CVE → log + PASS
  4. Check dependency depth against DEPENDENCY_DEPTH_REDLINE
  5. Check for deprecated/abandoned packages (no release >2yr, archived)
  6. Detect duplicate packages at different versions
  7. Verify license compatibility against declared policy

  PASS | MODEL_BOUND | VIOLATION
```

**Artifact:** `dependency_report.json`

---

### Gate 4 — EVIDENCE

**Purpose:** Evaluate the quality, independence, and agreement of evidence supporting the claim.

#### 4.1 Evidence Quality

```
clamp01(x) := max(0, min(1, x))

Quality(e) = clamp01(
  0.40 * provenance_score(tier)        // A=1.0, B=0.7, C=0.4
+ 0.25 * repeatability_score(method)   // repeatable=1.0, else=0.5
+ 0.20 * freshness_score(e)            // within TTL=1.0, expired=0.0, no TTL=0.8
+ 0.15 * environment_match_score(e)    // matches policy env=1.0, partial=0.5, unknown=0.2
)
```

#### 4.2 Independence Graph

```
Edge between e_i and e_j if:
  - same source_id
  - OR same tool + same config + |Δt| <= 60s (likely same CI run)
  - OR explicit dependency declared

MIS_GREEDY(G):
  Order by (degree ascending, id ascending)
  Greedily pick non-adjacent nodes
  Timeout → INCONCLUSIVE(MIS_TIMEOUT)
```

#### 4.3 Agreement

```
n < 2 → agreement = 1.0
Binary items:  agreement = count(pass) / n  (unanimous required for PASS)
Numeric items: pair_score = 1 iff intervals overlap within EPS, else 0
               agreement = (sum pair_scores) / (n*(n-1)/2)
```

#### 4.4 Evidence Gate Execution

```
EVIDENCE_GATE(claim):
  For each critical variable x:
    1. Build independence graph G_x from evidence items
    2. Compute S_x = MIS_GREEDY(G_x) — maximum independent set
    3. Require |S_x| >= Kmin
    4. Require agreement(S_x) >= Amin
    5. Require mean(Quality(e) for e in S_x) >= Qmin

  Thresholds (by regime):
    dev:     Kmin=2, Amin=0.70, Qmin=0.60
    staging: Kmin=2, Amin=0.80, Qmin=0.70
    prod:    Kmin=3, Amin=0.90, Qmin=0.80

  PASS
  or INCONCLUSIVE: INSUFFICIENT_INDEPENDENCE
                   LOW_AGREEMENT
                   LOW_QUALITY
                   MIS_TIMEOUT
```

**Artifact:** `evidence_report.json`

**Evidence Diversity (preserved from v1.0):**

Each critical variable SHOULD have evidence from at least two independent artifact types (e.g., AST analysis + runtime trace, unit test + mutation test). Single-type evidence is not rejected but is flagged in `evidence_report.json` for downstream audit visibility.

---

### Gate 5 — MATH

**Purpose:** Verify that declared constraints are satisfiable given the evidence.

```
MATH_GATE(claim):
  1. Bind evidence values to constraint variables
  2. Translate constraints to interval propagation or SMT
  3. Evaluate:
     - SAT (all constraints satisfied)   → PASS
     - UNSAT (constraint violated)        → VIOLATION(UNSAT_CONSTRAINT)
     - TIMEOUT (solver exceeds limit)     → INCONCLUSIVE(DECIDABILITY_TIMEOUT)
```

**Scope restriction:** Limited to the decidable fragment — linear real arithmetic (LRA), fixed-width bit-vectors, SI unit dimensional analysis, range bounding. Non-linear transcendental functions require an attached formal proof or accept `MODEL_BOUND(GODEL_CEILING)`.

**Artifact:** `math_report.json`

---

### Gate 6 — COST

**Purpose:** Verify resource consumption is within declared bounds.

```
COST_GATE(claim):
  1. Compute utilization: u = max_i(cost_i / bound_i)
     over all declared cost components
  2. Evaluate:
     - u < 0.80                      → PASS
     - 0.80 <= u < 0.95              → PASS with warning (logged)
     - u >= 0.95                     → MODEL_BOUND(COST_REDLINING)
     - cost component has no bound   → VIOLATION(UNDECLARED_COST_BOUND)

  PASS | MODEL_BOUND | VIOLATION
```

**Artifact:** `cost_report.json`

---

### Gate 7 — INCENTIVE

**Purpose:** Detect evidence source dominance. If one source controls >50% of evidence, the evidence set is compromised.

```
INCENTIVE_GATE(claim):
  For each critical variable x:
    1. Compute Dominance(x) = max_count_by_source / |S_x|
    2. If Dominance(x) > 0.75 → VIOLATION(EVIDENCE_CAPTURE)
    3. If Dominance(x) > 0.50 → MODEL_BOUND(DOMINANCE_DETECTED)

  Vendor concentration (build extension):
    1. Compute registry concentration across DependencyManifest
    2. If single registry provides >80% of packages → MODEL_BOUND(VENDOR_CONCENTRATION)

  PASS | MODEL_BOUND | VIOLATION
```

**Artifact:** `incentive_report.json`

---

### Gate 8 — SECURITY

**Purpose:** Dedicated security posture evaluation. Secrets detection, SAST findings, auth boundary review, crypto configuration.

**Dependency contract:** SECURITY gate MUST consume `type_report.json` from Gate 2 (TYPE), specifically the trust boundary map. If `type_report.json` is absent or does not contain a `trust_boundaries` field, SECURITY gate produces `VIOLATION(TYPE_SECURITY_LINK_FAILURE)` before any other checks execute.

```
SECURITY_GATE(claim):
  0. Verify type_report.json exists and contains trust_boundaries
     → If absent: VIOLATION(TYPE_SECURITY_LINK_FAILURE)

  1. If SecurityManifest.secrets_detected == true:
     → VIOLATION(SECRET_DETECTED)         // zero tolerance

  2. For each SASTFinding:
     - CRITICAL → VIOLATION(SAST_CRITICAL)
     - HIGH     → VIOLATION(SAST_HIGH)
     - MEDIUM   → MODEL_BOUND(SAST_MEDIUM) if policy allows
     - LOW      → log + PASS

  3. Verify auth_boundaries are declared and reviewed
  4. Verify injection_surfaces have declared mitigations
  5. Verify TLS min_version >= 1.2

  6. Cross-reference trust boundaries from TYPE gate (type_report.json):
     - Any trust boundary without declared mitigation → VIOLATION(UNMITIGATED_BOUNDARY)

  PASS | MODEL_BOUND | VIOLATION
```

**Artifact:** `security_report.json`

---

### Gate 9 — ADVERSARY

**Purpose:** Hostile verification. Fuzz, mutate, exploit, and stress-test.

```
ADVERSARY_GATE(claim):
  For each attack in AttackSuite:
    1. Apply perturbation:
       PerturbParam: param * (1 + delta_rel)

       delta_rel is deterministic:
         magnitude := 0.05 (fixed default, declared in PolicyHash)
         sign      := +1 if hash(attack.id) % 2 == 0, else -1
         delta_rel := sign * magnitude

       Reproducibility: given identical attack.id, delta_rel is identical.
       Custom magnitudes may be declared per-attack in AttackSuite;
       default is 0.05. All magnitudes are recorded in PolicyHash.

    2. Re-evaluate constraints under perturbed values
    3. If any constraint flips from SAT to UNSAT → VIOLATION(ADVERSARY_FRAGILE)

  Attack categories (build domain):
    - fuzz:                garbage/boundary inputs to API surfaces
    - mutation:            inject code mutations, verify test suite catches them
    - supply_chain:        simulate compromised dependency
    - outage_simulation:   simulate downstream service failure
    - load_spike:          simulate traffic burst beyond declared bounds
    - exploit:             targeted vulnerability exploitation

  Coverage threshold:
    All declared attack categories must execute.
    Incomplete coverage → INCONCLUSIVE(COVERAGE_INCOMPLETE)

  PASS | MODEL_BOUND | VIOLATION
```

**Artifact:** `adversary_report.json`

---

### Gate 10 — TRACE/SEAL

**Purpose:** Compute the cryptographic seal over the entire pipeline run.

```
TRACE_SEAL_GATE(claim, gate_results):
  1. Compute PolicyHash:
     PolicyHash = SHA256(canonical(
       version, hash_alg, solver_backend, timeouts,
       thresholds, attack_params, gate_order, attack_suite_hash
     ))

  2. Build trace chain:
     trace_0 = SHA256("GENESIS" + PolicyHash + ClaimID)
     trace_k = SHA256(trace_prev + canonical(gate_result_k))
       for k = 1..9

  3. Compute final seal:
     seal = trace_10 (final hash in chain)

  4. Write manifest:
     manifest.json = {
       claim_id:     ClaimID,
       env_hash:     ENV_HASH,
       policy_hash:  PolicyHash,
       gate_results: [hash of each gate report],
       final_verdict: max(all gate verdicts by precedence),
       seal:         seal,
       timestamp:    ENV_MANIFEST.timestamp
     }

  5. Append seal to S.E.A.L. ledger

  Always PASS (sealing is a recording operation, not an evaluation)
```

**Artifacts:** `trace.jsonl`, `manifest.json`, `seal.json`

---

## 6. Artifact Canonicalization (Preserved from v1.0)

All artifacts hashed by the SEAL MUST conform to canonical form before hashing:

```
CANONICAL_FORM:

  Encoding:    UTF-8 (no BOM)
  Format:      JSON
  Key order:   lexicographic (recursive — nested objects also sorted)
  Whitespace:  compact — no trailing, no indentation, no newlines
  Numbers:     no leading zeros, no trailing decimal zeros
  Strings:     double-quoted, escaped per RFC 8259
  Nulls:       literal "null" (not absent keys)
```

Binary artifacts are Base64-encoded into a JSON wrapper before canonicalization:

```json
{"_binary": true, "encoding": "base64", "data": "<base64 string>"}
```

---

## 7. Determinism Invariant (Preserved from v1.0)

Given identical `ENV_HASH`, identical input (same BuildClaim with same ClaimID), and identical `PolicyHash`:

The pipeline MUST produce identical `seal`. If it does not:
- Run is logged to S.E.A.L. ledger as `VIOLATION: NONDETERMINISM`
- Run output is invalidated
- Source of nondeterminism must be traced before re-run

**Explicitly scoped out:**
- System timestamps → use `ENV_MANIFEST.timestamp`
- Random seeds → seeded from `ClaimID` or declared fixed seed
- External API calls → classified as `MODEL_BOUND`, not run inline
- File system ordering → all lists sorted before hashing

---

## 8. State Evolution

```
Structural edit (new primitive, boundary, operator):
  → New ClaimID
  → Full pipeline re-run from Gate 1

Evidence update (new test results, same commit):
  → Same ClaimID
  → Re-run from Gate 4 (EVIDENCE)

Environment change (dependency update, language version):
  → New ENV_HASH
  → Full pipeline re-run from Gate 1
  → Previous seal is invalidated (EPISTEMIC_DECAY in v1.0 terms)
```

---

## 9. Reason Codes (Complete Index)

| Gate | Code | Meaning |
|---|---|---|
| INTAKE | `INTAKE_MALFORMED` | BuildClaim parse failure |
| INTAKE | `INTAKE_COMMIT_MISMATCH` | Commit hash doesn't match HEAD |
| INTAKE | `INTAKE_LOCKFILE_DRIFT` | Lockfile hash doesn't match disk |
| TYPE | `UNDEFINED_SYMBOL` | Constraint references undeclared primitive |
| TYPE | `UNIT_MISMATCH` | Incompatible units across operator |
| TYPE | `ARITY_ERROR` | Operator input count wrong |
| TYPE | `EMPTY_DOMAIN` | Primitive domain has no valid range |
| DEPENDENCY | `CVE_CRITICAL` | Critical/high CVE with no patch |
| DEPENDENCY | `CVE_MEDIUM` | Medium CVE (MODEL_BOUND if policy allows) |
| EVIDENCE | `INSUFFICIENT_INDEPENDENCE` | |S_x| < Kmin |
| EVIDENCE | `LOW_AGREEMENT` | agreement(S_x) < Amin |
| EVIDENCE | `LOW_QUALITY` | mean Quality < Qmin |
| EVIDENCE | `MIS_TIMEOUT` | Independence solver timed out |
| MATH | `UNSAT_CONSTRAINT` | Constraint violated by evidence values |
| MATH | `DECIDABILITY_TIMEOUT` | SMT solver exceeded time limit |
| MATH | `GODEL_CEILING` | Non-linear claim, no formal proof attached |
| COST | `UNDECLARED_COST_BOUND` | Cost component with no declared bound |
| COST | `COST_REDLINING` | Utilization >= 0.95 |
| INCENTIVE | `EVIDENCE_CAPTURE` | Single source >75% of evidence set |
| INCENTIVE | `DOMINANCE_DETECTED` | Single source >50% of evidence set |
| INCENTIVE | `VENDOR_CONCENTRATION` | Single registry >80% of packages |
| SECURITY | `TYPE_SECURITY_LINK_FAILURE` | type_report.json absent or missing trust_boundaries |
| SECURITY | `SECRET_DETECTED` | Secrets in codebase (zero tolerance) |
| SECURITY | `SAST_CRITICAL` | Critical SAST finding |
| SECURITY | `SAST_HIGH` | High SAST finding |
| SECURITY | `SAST_MEDIUM` | Medium SAST finding (MODEL_BOUND if policy) |
| SECURITY | `UNMITIGATED_BOUNDARY` | Trust boundary with no declared mitigation |
| ADVERSARY | `ADVERSARY_FRAGILE` | Constraint flips under perturbation |
| ADVERSARY | `COVERAGE_INCOMPLETE` | Not all attack categories executed |
| PIPELINE | `PIPELINE_ORDER_MISMATCH` | Gates executed out of order |
| PIPELINE | `NONDETERMINISM` | Same input produced different output |

---

## 10. Integration

| System | Role |
|---|---|
| **omega-brain-mcp** | Hosts the 10-gate pipeline; exposes `veritas_run_pipeline`, `veritas_compute_quality`, `veritas_mis_greedy`, `veritas_claeg_resolve`, `veritas_claeg_transition` as individual MCP tools; appends `seal` to S.E.A.L. hash chain |
| **AEGIS / AEGIS-Rewrite** | Tier 1: receives VIOLATION records, applies deterministic fixes. Tier 2: receives MODEL_BOUND records for AI-assisted remediation under constraint envelope. |
| **Gravity-Omega** | Execution host; enforces VTP signature on gate outputs before downstream routing |
| **Veritas Vault** | Archives seal, ENV_MANIFEST, all gate report hashes via `omega_log_session` |
| **S.E.A.L. Ledger** | Append-only chain of seal values; NONDETERMINISM violations logged as ledger entries |

---

## 11. Delta from Ω-CODE v1.0

| v1.0 Concept | v2.0 Status | Notes |
|---|---|---|
| CLAEG EBNF grammar | Replaced by BuildClaim object model | Structured objects align with omega-brain-mcp JSON schema |
| Gate 0 (CLAEG) | Absorbed into INTAKE + TYPE | Parsing → INTAKE; symbol validation → TYPE |
| Gate 4 (AUTHORITY) | Absorbed into MATH + SECURITY | Spec compliance → MATH constraints; runtime rules → SECURITY |
| Gate 5 (SOLVENCY) | Absorbed into MATH + ADVERSARY | State model → MATH (SMT constraint satisfaction); state reachability → ADVERSARY (exploit simulation) |
| Gate 7 (TEMPORAL) | Absorbed into ADVERSARY | Race conditions, async ordering → fuzz/mutation testing in ADVERSARY |
| REJECTED_AT_CLAEG | Removed | INTAKE and TYPE cover all parse/validation failures |
| EPISTEMIC_DECAY | Removed (semantics preserved) | ENV_HASH change → State Evolution rule (Section 8): full re-run |
| CASCADED_FAIL | Removed | Fail-fast rule (Section 4.2) halts pipeline; no downstream gates run |
| ENV_MANIFEST | Preserved | Unique to Ω-CODE; not in base v1.3.1 or Build spec |
| Artifact canonicalization | Preserved | Unique to Ω-CODE; critical for cross-system verification |
| Trust boundary definition | Preserved | Feeds into SECURITY gate (Gate 8) |
| Evidence diversity rule | Preserved (softened) | Flagged rather than hard-rejected; logged in evidence_report |
| Execution bounds | Replaced by PolicyHash timeouts | Solver timeouts, search limits declared in PolicyHash |
| Scope resolution | Replaced by UNDEFINED_SYMBOL check | TYPE gate validates all constraint symbols against declared primitives |
| Per-claim + run-level SEAL | Replaced by trace chain | trace_k = H(trace_prev + canonical(gate_result_k)) per TRACE/SEAL |

---

## 12. What Is Not In Scope

Ω-CODE does not:
- Reason narratively about code quality, style, or intent
- Produce probabilistic severity scores (use AEGIS for triage)
- Evaluate claims that cannot be expressed as structured BuildClaim objects (these are rejected at INTAKE, not approximated)
- Replace formal verification for safety-critical systems (it enforces deterministic pipeline discipline, not theorem proving)
- Model epistemic entropy, fractal composability, or causal do-calculus (these are v2.0+ metasystem extensions per the VERITAS roadmap)

---

*VERITAS Ω-CODE v2.0 — SEALED: SHA256:637e324085b94b26493234afa756236f3dc104f377693aaa141a1faca686a90a*  
*Lineage: v1.0 (8-gate CLAEG) → Ω Build v1.0.0 (10-gate BuildClaim) → v2.0 (unified)*  
*Maintained at: veritas-docs / VRTXOmega*
