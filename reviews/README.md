# Shared ensemble-config rationale

Every field in `reviews/<review>/config.json` except `default_prompt` is identical across
all three reviews by design (README §4) — `vendors`, `aggregation`, `tau`, `batch_size`,
`zero_policy`, `confidence_threshold` are the one fixed instrument being proven reliable
across reviews, so it must not vary between them. This file explains what each of those
shared fields means and why it's set the way it is, so that reasoning doesn't need
repeating (and independently drifting) in three `_notes` arrays or in the README.

Each review's own `config.json`'s `_notes` carries only what's specific to that review:
the `default_prompt`-verified-against-source note.

This file is documentation only, like each config's `_notes` — the kernel loader
(`attest.cli._load_ensemble_config`) never reads it. Git history has the "who changed what
when"; this file only has to stay true to the current config.

## vendors (x = 4)

Four distinct vendor families, all pinned to a same-level, current-generation model —
"same level" meaning each vendor's balanced production-flagship tier (not its cheapest
fast/mini tier, and not its priciest specialized-reasoning tier above that), so the
ensemble compares vendors, not vendor A's flagship against vendor B's budget tier:

- Anthropic `claude-sonnet-5` — Anthropic's balanced production tier (Opus/Fable sit above
  it; Haiku below).
- Mistral `mistral-large-2512` — Mistral's flagship general-purpose model.
- OpenAI `gpt-5.6-terra` — the GPT-5.6 family's "balance intelligence and cost" tier (Sol is
  the frontier tier above it, Luna the budget tier below), the closest level match to
  Sonnet: both land at the same ~$2-3 input / ~$10-15 output per-1M-token price point, and
  both occupy the "recommended for production" position in their vendor's lineup rather
  than the top-of-line reasoning-flagship position.
- Google `gemini-3.1-pro-preview` — Google's current flagship reasoning model, also priced
  at the same ~$2 input / ~$12 output per-1M-token level as Sonnet/Terra.

**Being this current also means fighting temperature control on three of the four** —
current-generation "adaptive reasoning" models across vendors have broadly moved away from
honoring an explicit sampling `temperature`. See "## temperature" below for the per-vendor
finding and fix; it doesn't change which models are pinned here, only how each one is
called.

**Known risk, not a TODO:** `gemini-3.1-pro-preview` is, as its name states, a preview
endpoint — Google has no GA release at this capability tier as of 2026-08-24. Its
predecessor, `gemini-3-pro-preview`, was deprecated and shut down with about three weeks'
notice (2026-03-09), so this pin carries a real chance of needing to be re-pinned to a
newer preview or GA id mid-project, on Google's timeline rather than this project's. This
is a genuine reproducibility risk for `ensemble_config_id` (a forced re-pin opens a new
epoch, same as any other model change) — re-check `gemini-3.1-pro-preview`'s status before
freezing a real run, and again before starting any subsequent review's run.

Anthropic's dateless `claude-sonnet-5` is not a floating alias: per Anthropic's model-ID
documentation, dateless IDs from the Claude 4.6 generation onward are themselves pinned
snapshots, not evergreen pointers. OpenAI's `gpt-5.6-terra` is likewise a specific named
release, not an evergreen alias (OpenAI's `gpt-5.6` bare alias, unlike `-terra`, does
float — it currently routes to `gpt-5.6-sol` and isn't used here for that reason).

The Mistral vendor requires the `attest[mistral]` extra (`mistralai>=2.9.1`, already
included in `attest[all]`) and `MISTRAL_API_KEY`.

`model_version` is `TODO:capture-served-snapshot-before-freeze` on all four vendors.
Replace each with the exact dated snapshot the vendor's API confirms it served (many
vendors echo this back in the response) before freezing `data/run/` for epoch 1, so
`ensemble_config_id` is reproducible — this requires a live API call per vendor, so it
can't be resolved from documentation alone. It's not just documentation debt either: the
kernel checks `model_version` against what each vendor's own response reports and raises
`ModelVersionDriftError` on mismatch (skipped only for Google, whose response doesn't
expose it) — anthropic/openai/mistral will hard-fail on the first live call until the
TODOs are resolved.

## tau

`tau = 0.5386751345948129` (~0.5387). A vendor's actual vote is one of three categorical
decisions, `E`/`U`/`I` (exclude/uncertain/include — see default_prompt/track_prompts
below); the kernel translates each to a number, `-1`/`0`/`+1` respectively, purely so that
dispersion — a sample standard deviation — is a well-defined arithmetic operation over an
ensemble's votes. That numeric encoding is a convention adopted for this one computation,
not a restatement of what the vote is. Under it, at x = 4, a non-boundary vote vector's
sample standard deviation (n-1 denominator) can only land on one of two values: ~0.577
from an even 2-2 split such as `(1,1,0,0)`, or 0.5 from a 3-1 split such as `(1,1,1,0)` —
any vector mixing a -1 and a +1 is already caught by the boundary indicator, not the
dispersion term. tau is the midpoint of those two, `(0.5 + sqrt(1/3)) / 2`, via
`attest.ensemble.tau.resolve_tau(TIE_POLICY_ESCALATE, x=4)`: a 2-2 split has
`s ~= 0.577 > tau` and escalates, a 3-1 majority has `s = 0.5`, not `> tau`, so it still
auto-labels. A round number like 0.75 would sit above both attainable values and never
fire the dispersion criterion at all, silently reducing escalation to the boundary rule
alone — so tau has to be derived from x, not picked by hand, and must be recomputed
(`resolve_tau`) if x ever changes; it isn't comparable across ensemble sizes.

`attest.ensemble.tau.validate_tau` re-derives and checks this tau against x automatically
at `attest screen` epoch-open time, persisting the proof to `data/run/tau_report.json`
(surfaced under `tau_report` in `validate`'s output) — so this reasoning is cross-checked
by the kernel on every run, not just at config-authoring time. `attest ablate` takes the
same tau at face value across its whole x-sweep (Makefile's `TAU` var, README §5 step 7);
since the attainable-dispersion set depends on x, one fixed tau isn't behaviorally
comparable in strength across the swept subset sizes x' < 4 — xsweep attaches each
subset's own `describe_tau()` to the ablation report and warns once per sweep, which is
expected and needs no config change.

## batch_size

`attest.provenance.config.Config.batch_size` ("b_e" in the manuscript's `C_e` tuple) is the
number of records `attest` packs into one vendor screening request — a request-packing
width, not a corpus-size assertion. It is hashed into `ensemble_config_id`
unconditionally, on par with `vendors`/`aggregation`/`tau` — a change to it opens a new
epoch, same as any of those.

It's hashed, not just a throughput setting, because batch size measurably changes model
behavior, not merely cost/latency: Fagerberg et al., "Batch Size Effects on Mid-2025
State-of-the-Art Large Language Model Performance in Automated Title and Abstract
Screening" (*Cochrane Evidence Synthesis and Methods*, 2026;
[10.1002/cesm.70082](https://doi.org/10.1002/cesm.70082)), found sensitivity/specificity
shifting with batch size in a model-dependent, non-monotonic way when packing multiple
references into one prompt — e.g. GPT-5 mini's sensitivity fell from 0.88 at batch 200 to
0.48 at batch 400, while Gemini 2.5 Flash's sensitivity was low at batch 1 and rose with
larger batches. A `batch_size` change is therefore a change to the instrument itself, the
same epoch-opening category as a model or prompt change — not a value `attest` is free to
vary silently between runs.

Set to `1` explicitly in every checked-in `reviews/<review>/config.json`: one record per
request, matching this pipeline's actual instrument (§4/§6 — one record at a time, four
vendors voting independently on it, no request-level pooling). `attest` itself defaults
`batch_size` to `1` when a config omits it, so leaving it out here would behave
identically — it is set explicitly anyway so this file states its instrument outright,
the same way `aggregation`/`tau`/`zero_policy` are stated outright rather than relied on
as unstated kernel defaults.

`attest` chunks up to `batch_size` records into one request (grouped by resolved prompt
first), so a value above `1` would pack that many records into a single request per
prompt group per vendor, across all four vendors used here — every provider `attest`
supports packs multiple records into one request the same way, so this is a real choice
of instrument, not a vendor-capability constraint.

## default_prompt / track_prompts

`default_prompt` is what the kernel actually reads to screen every record:
`attest.provenance.config.Config.prompt_for_track` falls back to `default_prompt` for any
record whose track has no `track_prompts` entry, and these files carry no `track_prompts`
at all, so every record in a run gets this one prompt regardless of its track. This is
deliberate: the runbook proves attest's core mechanism (read title/abstract, apply one
instruction, four vendors vote, decide escalate-or-not) by running the whole pipeline
independently once per SYNERGY review — one list, one prompt per run — rather than pooling
multiple reviews' different eligibility questions into one run via `track_prompts`
routing. See README §6 for why: the reviews are different screening questions (different
domains, different criteria), not repeats of the same measurement, so a multi-track pooled
run was never the right design. `track_prompts` stays a valid, unused field for that
reason, in case a future pooled run ever needs it.

To add a review that doesn't yet have its own `reviews/<review>/` subfolder, see README
§2: copy `example_config.json`, look up that review's real `eligibility_criteria` in
`asreview/synergy-dataset`'s `datasets.toml`, and verify it word for word.

`prompt_version` (currently `v3`) is a provenance label only — the kernel never reads it
back (`attest.provenance.config.VendorSpec`) — so bump it by hand whenever `default_prompt`
changes, or it'll misrepresent what ran. Its text must carry only eligibility criteria,
never a trailing output-format instruction of its own:
`attest.vendors.base.compose_system_prompt` already appends its own `OUTPUT_CONTRACT` —
currently "Respond with exactly one letter and nothing else: E to exclude, U if related
but uncertain, or I to include." — to every criteria string on every rater path (sync,
batch, `DeterministicRater`), and warns if the supplied criteria already contains a copy
of it. A vendor's raw reply is a single letter for tokenizer reasons (some vendors split a
numeral like "-1" into two tokens, which used to skew `attest.ensemble.confidence`); the
kernel immediately parses it back to the ordinal `-1`/`0`/`+1` (`E`/`U`/`I` respectively)
that every aggregation/tau computation below actually operates on, so vote arithmetic is
unaffected by the wire-format letter.

## zero_policy

`zero_policy = "escalate"` governs the one case the boundary+dispersion rule can't resolve
by sign alone: a non-boundary vote vector whose mean lands exactly on 0 (e.g. all four
vendors vote 0). `Decision.auto_label` can never be 0 — ordinal 0 has no place in the
gold-binary confusion matrix, so a 0 there would otherwise silently become a fabricated
false negative or false positive downstream. Under `"escalate"` (the recall-safe choice,
used here) a would-be 0 routes to human adjudication like any other escalation; the only
other option is `"include"` (folds it into +1) — there is deliberately no `"exclude"`
option, since that's the one disposition that would silently destroy recall. See
`attest.ensemble.aggregate.g`/`_boundary_dispersion`. This repo's `src/score_audit.py`
only maps drawn record ids to SYNERGY gold labels for `audit-apply` and never itself
branches on a predicted/auto label, so it needs no zero-handling of its own.

## temperature

The design intent is deterministic sampling for a screening task where reproducibility
matters more than response diversity, and `attest.provenance.config.VendorSpec.temperature`
is required with no default — `_load_ensemble_config` reads `spec['temperature']` directly,
so a vendor entry missing it raises `KeyError` at load time. It's hash-sensitive: changing
it changes `ensemble_config_id` and opens a new epoch, same as `model_version`/`prompt_version`.

**It is not literally `0.0` for all four vendors, because two of the four current-generation
models don't let it be** (found live, 2026-08-24, not assumed from documentation):

- **anthropic (`claude-sonnet-5`)**: `temperature: 0.0` plus `"send_temperature": false`.
  Sonnet 5 (and the rest of the Claude 4.6+ generation) rejects any explicit
  `temperature`/`top_p`/`top_k` value with HTTP 400, confirmed against Anthropic's own
  current model documentation — no parameter analogous to OpenAI's `reasoning_effort`
  re-enables it. `send_temperature: false`
  (`attest.provenance.config.VendorSpec.send_temperature`, kernel commit `da977f3`+) tells
  `AnthropicRater`/`AnthropicBatchRater` to omit `temperature` from the Messages API request
  entirely rather than send a value the vendor rejects outright. `temperature` itself stays
  `0.0` in the file as provenance of the *requested* value, even though it can't be honored.
- **openai (`gpt-5.6-terra`)**: `temperature: 0.0` plus `"reasoning_effort": "none"`.
  Confirmed live against this exact review's `default_prompt` and a real `data/gold.json`
  record: `temperature=0.0` alone returns HTTP 400 ("Only the default (1) value is
  supported"); adding `reasoning_effort="none"` makes the same call succeed.
  `reasoning_effort` (`VendorSpec.reasoning_effort`, kernel commit `da977f3`+) is forwarded
  to `OpenAIRater`/`OpenAIBatchRater` only when set, so this is additive, not a fallback.
- **google (`gemini-3.1-pro-preview`)**: `temperature: 1.0`, deliberately *not* matching the
  other three. Google's own guidance: "leaving temperature at 1.0... lower values degrade
  reasoning quality... can cause looping" on Gemini 3.x thinking models — a real correctness
  risk, not a hard 400 like the two above, so this one is set to the vendor's own recommended
  default rather than fought.
- **mistral (`mistral-large-2512`)**: unaffected, `temperature: 0.0` works as a normal
  parameter — not a reasoning-gated model.

Both `reasoning_effort` and `send_temperature` are optional `VendorSpec` fields, hashed into
`ensemble_config_id` only when set to something other than their no-op default (`None` and
`True` respectively) — a config that never sets them hashes identically to one written
before these fields existed. Requires the local `attest` kernel clone's commit `da977f3` or
later; not yet pushed to `herbertkokholm/attest`'s `main` as of 2026-08-24, so a fresh
`pip install` of the `git+https://...` dependency won't yet pick this up — see README §4.

## confidence_threshold

`confidence_threshold = 0.5` is the default `low_threshold` a confidence-stratified
audit-draw uses when its own `--confidence-threshold` flag isn't passed
(`attest.ensemble.confidence.DEFAULT_LOW_THRESHOLD` is also 0.5, so this is set explicitly
here purely for clarity, not because omitting it would behave differently). Unlike
`temperature`, it's deliberately excluded from `to_dict()`/`ensemble_config_id`
(`attest.provenance.config.Config` docstring): it only changes how an already-fixed
excluded population is stratified for audit, never what a vendor samples or the ensemble's
aggregate decision, so changing it doesn't open a new epoch.

## What each config.json's _notes actually covers

Each `reviews/<review>/config.json` is not read literally beyond `vendors` (including
each vendor's `temperature`), `aggregation`, `tau`, `batch_size`, `zero_policy`,
`default_prompt`, `track_prompts`, and `confidence_threshold` (see
`attest.cli._load_ensemble_config`) — `_notes`, and this file, are ignored by the loader
and safe to keep as documentation. `attest screen` reads `config.json` directly (see the
Makefile's `screen` target); there is no separate resolved/patched copy.
