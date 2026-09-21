# Conservative installed-input adapters

## Goal and plan, issue #119

Keep the current Workflow Studio compiler, schema fingerprint, authoring format
and native execution boundary. Replace silent input-schema simplification with
one shared conservative normalization path. Unsupported data remains evidence,
not an executable guess. No plugin code, URL, model or widget script is invoked.

Implementation order:
1. Lock existing schema contracts at main `67f995f245518b36fb0192a61da780d337d53028`.
2. Reproduce malformed whole input containers, null groups, duplicate/shadowed
   names, extra tuple fields, truthy non-boolean flags and empty union sockets.
3. Normalize through `studio_workflow.node_inputs`; consume the same result in
   the existing catalog, compiler and all current catalog-based clients.
4. Preserve full node definitions and descriptors as canonical JSON text, not
   already-rounded browser numeric objects. Run real Node JSON transport tests.
5. Check legacy compiler parity, self-review and publish only the tested files.

## What is now enforced

An absent input declaration may describe a real zero-input node. A present but
malformed `input`, `inputs`, `required`, `optional` or `hidden` declaration cannot.
Mixed legacy and v2 containers, unknown groups, and duplicate names across groups
produce node-local schema errors. A malformed legacy field cannot fall through
into an apparently valid v2 definition. Healthy disconnected branches still
compile, while malformed selected output closures remain blocked.

A tuple must contain a type and at most one options object. Extra fields, null
options, conflicting legacy choices, malformed semantic booleans and empty socket
tokens become visible unsupported inputs. Invalid hidden flags cannot conceal a
required unsupported field. The compiler emits no graph for those active inputs;
the existing inspector already displays their reason and retains their values.
An omitted unsupported optional field still does not invent a requirement.

The adapter identifiers are `scalar-int/v1`, `scalar-float/v1`,
`scalar-string/v1`, `scalar-boolean/v1`, `scalar-combo/v1`,
`typed-connection/v1`, and `native-required/v1`. Their capability record separates
static validation, document round-trip retention, and runtime qualification.
`runtime_qualified` is always false: installed metadata is not an execution test.
Force-input connections, lazy annotations, wildcard/union sockets, native-only
remote/raw-link/dynamic behavior and strict typed combos retain existing meaning.
List and hidden injection declarations remain runtime-owned and are retained in
node evidence. `input_is_list`, when present, must be a boolean.

## Lossless retention and precision boundary

Each normalized node exposes `source_definition_json`; each authorable descriptor
exposes `source_descriptor_json`. These are inert **JSON text strings**, preserving
all parsed metadata, nested unknown fields, tuple tails, integer values and JSON
integer-versus-float representation. They preserve semantic JSON, not original
whitespace, duplicate keys, encoding or raw byte spelling. Existing source-schema
SHA-256 still binds the complete input definition; the document format is unchanged.

Keep these fields as text through browser transport. Parsing their contents with
ordinary JavaScript `JSON.parse` would reintroduce precision loss. They are not
new widget values or automatic execution payloads. The existing normalized options
still serve existing controls; they are not the lossless evidence owner.

The Python document/compiler path continues to support exact signed and unsigned
64-bit INT values. The browser's existing refusal of unsafe document integers is
unchanged. This PR does **not** implement a BigInt editor, raw-number HTTP protocol,
or a typed numeric-combo browser adapter. Retained schema text is not a claim that
all numbers can now be edited in a browser. Safe refusal remains preferable to
silently changing a seed.

Full evidence adds catalog payload overhead (node JSON plus descriptor JSON).
No installed large-catalog memory/latency qualification is claimed. A later lazy
evidence endpoint may reduce duplication but must retain the same identities;
never drop unknown fields to make a response smaller without disclosing it.

## Local verification, 19 September 2026

Linux, Python 3.13.5, Node v22.16.0. Pinned original `core.py`, `node_outputs.py`,
package initializer and original schema tests were fetched through the GitHub
connector and verified against their Git blob IDs. Direct cloning was unavailable.
All tests imported the actual full core, not AST excerpts or mocked compilers.

- Original `test_workflow_schema_contracts.py`: **8 tests passed**, before and after.
- New `test_workflow_input_adapters.py`: **9 tests passed**, including parameterized
  malformed descriptors/containers, exact int64 boundaries, disconnected opaque
  retention, safe static capabilities and real Node JSON serialization.
- Initial regression run: **34 failed subcases, 3 errors**; all became green with
  the production adapter change.
- `python -m unittest discover -s tests -p 'test_workflow_*.py' -v`: **17 passed,
  zero skipped**, in the fetched subset.
- **600 seeded supported-schema comparisons** against the pinned original full
  compiler: identical documents and complete compilation reports, including
  64-bit integers, typed combos, strings, booleans and floating-point values.
- `python -m compileall -q studio_workflow tests` and scoped `git diff --check`: pass.

Direct self-review checked optional-input behavior, hidden-name shadowing,
malformed-container fallback, integer retention, source immutability, schema
fingerprints and selected-closure isolation. No Codex review or cloud Actions
results were used.

Remaining #119 acceptance: captured installed-node corpus/provenance, richer custom
widget adapters, native round trips, full browser/HTTP qualification, full
repository regression/validator, and Windows runtime. The narrow software paths
above are tested; these broader gates remain open. No model jobs, installs,
backend switches, project decisions or saved document migrations were performed.
