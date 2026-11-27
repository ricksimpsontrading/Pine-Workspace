# Graphics annex — reader contract v1 (`pws-graphics-reader-v1`)

EXPERIMENTAL, isolated study copy. This is a **reader** contract: what the reader
(`tools/pws_workspace/annex_reader.py`, stdlib only, no display), the local test path
(`tools/pws_workspace/local_test.py`) and the browser chart (`tools/pws_workspace/live.py`,
`tools/vela_view/page/pws-view.js`, Vela) accept, check and display. The browser chart is the
only viewer; the former terminal viewers (iTerm2, Terminal.app) are withdrawn and never shipped.

It does not change what the runner writes:

- The runner keeps writing `pws-pinets-graphics-v0.2-exp` (`tools/pine_exec/graphics.mjs`,
  `runner.mjs`).
- Neither file is modified by this contract. The executor fingerprint and the calibrations are
  therefore unchanged.

## 1. Versions

| Annex `schema` | Reader behaviour |
|---|---|
| `pws-pinets-graphics-v0.2-exp` | read under its own rules (§3, §4), with its own run report; never converted, never completed |
| `pws-pinets-graphics-v0-exp`, `pws-pinets-graphics-v0.1-exp` | refused, `LEGACY`: the run report records no SHA-256 of the annex |
| anything else | refused, `UNKNOWN_SCHEMA` — even when the report declares the same schema and the SHA-256 matches |

The version of origin is shown to the user:

- in the side panel of the browser page (`annexe v0.2-exp`);
- in the output of `local-test run|open`, under `open.annex_schema` and `open.version_note`.

## 2. Fields PRODUCED by the writer v0.2-exp

This section describes what the files contain. It is not a list of what the reader checks (see §3).

**Run report (`run.json`, schema `pws-pinets-run-v1`).**

The run report holds:

- the identity fields of §3;
- `execution_status`;
- `normalized` (the canonical payload);
- `normalized_payload_sha256`.

When the annex was requested, the run report also holds a `graphics_annex` object with:

| Field | Content |
|---|---|
| `schema` | the annex schema |
| `path` | absolute path where the annex was written |
| `status` | `GRAPHICS_WRITTEN`, `GRAPHICS_EXTRACTION_FAILED`, `GRAPHICS_WRITE_FAILED` or `GRAPHICS_WRITE_UNVERIFIED` |
| `sha256` | SHA-256 of the annex bytes as read back, or null |
| `error` | null, or `{stage, message}` |
| `file_state` | what is really at the destination |

**Annex (`graphics.json`).**

| Field | Content |
|---|---|
| `schema` | `pws-pinets-graphics-v0.2-exp` |
| identity | the seven fields of §3, copied from the report |
| `declaration` | indicator declaration keys copied **if present**: `title`, `shorttitle`, `overlay`, `format`, `precision`, `scale`, `max_*_count`, `max_bars_back`. Neither `title` nor `overlay` is guaranteed: the reader falls back to the report path and to `overlay: false`. |
| `series[]` | `key`, `title`, `callsite` (string or null), `kind`, `options` (object), `points[]` |
| `series[].kind` | `line` when no style is given; else `shape`, `char`, `hline`, `background`, `fill` or `barcolor`; else **the raw engine style** as a string (e.g. `style_histogram`, `candle`) |
| `series[].points[]` | `t` (integer time); `v` (number, **boolean**, or null); optional `ohlc` (`[o,h,l,c]` for plotcandle/plotbar, `v` then null); optional `color`; optional `o` (per-point options) |
| `drawings` | object mapping a family (`boxes`, `labels`, `linefills`, `lines`, `polylines`, `tables`) to the list of objects alive at the end of the run |
| `drawings_scope` | `"final-state"` |
| `limits` | a **list of texts**, informative |

## 3. Checks PERFORMED by the reader v1

The reader runs these checks in order, before any display, and stops at the first refusal.
It only reads the three files.

| # | Check | Refusal code |
|---|---|---|
| 1 | dataset, report and annex files exist and are JSON objects | `MISSING` / `MALFORMED` |
| 2 | report `schema` is `pws-pinets-run-v1` and `execution_status` is `PINETS_EXECUTION_PASS` | `REPORT_INVALID` |
| 3 | annex `schema` is a legacy version | `LEGACY` |
| 4 | annex `schema` is a version this reader knows (§1) | `UNKNOWN_SCHEMA` |
| 5 | the seven identity fields are typed: four lowercase SHA-256 values (`source_sha256`, `dataset_sha256`, `executor_fingerprint`, `normalized_payload_sha256`) and three non-empty strings (`run_id`, `pinets_version`, `normalization_schema`), in both report and annex | `MALFORMED` |
| 6 | report `graphics_annex.sha256` is a lowercase SHA-256 and `graphics_annex.error` is empty | `REPORT_INVALID` |
| 7 | report `graphics_annex.schema` equals the annex `schema` | `SCHEMA_MISMATCH` |
| 8 | SHA-256 of the annex bytes equals report `graphics_annex.sha256`; when it differs, an annex `run_id` different from the report's gives `OTHER_RUN`, otherwise `ALTERED` | `OTHER_RUN` / `ALTERED` |
| 9 | the seven identity fields are equal between annex and report | `OTHER_RUN` |
| 10 | the report payload, put in canonical form (port of `normalize.mjs`), hashes to `normalized_payload_sha256` | `REPORT_INVALID` |
| 11 | report `dataset_sha256` equals the SHA-256 of the dataset file | `OTHER_DATASET` |
| 12 | annex shape, under the rules of its version (see the v0.2-exp details below) | `MALFORMED` |
| 13 | annex series keys equal the payload plot keys; each point has the payload time; its value, rounded to **12 significant digits** (port of `roundValue`: `toPrecision(12)`, and non-numbers such as booleans give null), equals the payload value | `MALFORMED` |
| 14 | the times of every series equal the dataset times | `OTHER_DATASET` |

Shape rules of v0.2-exp (check 12):

- `declaration` is an object.
- Every series has a string `key`, a string `kind`, an object `options` and a list `points`.
- `t` is an integer.
- `v` is a number, a boolean or null.
- `drawings` maps only the six families to lists.
- `drawings_scope` is `"final-state"`.
- `limits` is a list of texts.

The reader does **not** check:

- `graphics_annex.status`, `path` and `file_state`;
- `ohlc`, `color` and `o`;
- the content of the drawing objects.

A passing check proves that the files are **consistent** with each other, not that they are
authentic: there is no signature.

## 4. Drawings: what is guaranteed

The reader contract v1 guarantees, for each of the six families, only **the family and the number
of objects** recorded in their final state (`drawing_counts`).

The fields of a drawing object are not guaranteed:

- they come from the internal structures of the engine (PineTS);
- they may change with the engine;
- the browser page draws none of them: it lists them as not shown, with their family and count.

The browser page draws the line-family series (`line`, `style_line`, `style_linebr`, and
`style_stepline` as a step line) and the `hline` levels; any other series kind is listed as not
shown.

## 5. Scope of "objects in final state"

**Drawings** are the objects alive at the end of the single run, with their final properties:

- a deleted object is absent;
- a moved object is at its last position;
- there is no per-bar history.

**Series** are the per-bar values of that same run on closed bars. They are bound to the hashed
payload. There is no intrabar or realtime view.

The notice is always displayed by the browser page, in its side panel: *moving the cursor to an old
candle does not necessarily rebuild what was known at that time* (in French: « ne reconstitue pas
nécessairement ce qui était connu à cet instant »).

## 6. Refusals keep the numeric result

On a refusal of the reader:

- `local-test open` (an earlier test) opens nothing and exits with code 4, with `refusal_code`,
  `refusal_detail` and a localized `open_refused`;
- `local-test run --graphics` reports the same fields and exits with code 5 (computation PASS);
- a page opened on such a run shows `Preview refused [CODE]: <localized message>. The numeric
  result of the report stays valid.` and no chart;
- the run report, its `execution_status` and its numeric payload are never modified;
- PineTS is never called: neither the page nor `local-test open|view` starts the runner.

Without the browser chart in an installation (package built without the optional `vela-view`
component, or its dependencies not installed), a chart request is refused with `VELA_ABSENT` or
`VELA_NO_DEPS` (exit code 7), for the same reasons: nothing is recomputed, the report is untouched.

Codes are stable. Their messages are localized (fr, en) in `annex_reader.REFUSAL_TEXT`:

- `MISSING`
- `MALFORMED`
- `REPORT_INVALID`
- `UNKNOWN_SCHEMA`
- `LEGACY`
- `SCHEMA_MISMATCH`
- `ALTERED`
- `OTHER_RUN`
- `OTHER_DATASET`

## 7. Files

The reader and the page read the report, the annex and the dataset, and never write them. Opening
a chart writes only its page (`index.html`) and its `frame.js` under
`.claude/runtime/vela-view/<work-slug | run-run_id>/`.
