# Preserved capture-contract follow-up (earlier delivery)

This is the **exact, complete public source patch** from the earlier chat delivery,
including its implementation, tests, owned profile, design, plan and usage guide.
It was not present at `studio_workflow/dcc_capture_contract.py` on main
`686411437a9c3264434851c4624ff8a2cf3b0621` when this continuation checked.

The patch is stored as a compact zlib source archive, not installed or imported.
`manifest.json` pins its compressed and original bytes and lists all six paths.
No private research export, character asset, local configuration or binary model
is included. Preservation is **not** a claim of integration or current qualification.
Its original baseline/dependency assumptions are historical and must be reconciled
with the current native producer before any application. Do not blindly apply it.

Restore the original patch to a **new file** from the repository root:

```console
python -c "import hashlib,json,pathlib,zlib; p=pathlib.Path('research/agentic-creation/archive/capture-contract-followup'); m=json.loads((p/'manifest.json').read_text()); b=zlib.decompress((p/'source.patch.zlib').read_bytes()); assert len(b)==m['original_bytes'] and hashlib.sha256(b).hexdigest()==m['original_sha256']; f=open('capture-contract-followup-restored.patch','xb'); f.write(b); f.close()"
```

This command does not apply or execute the patch. The archived guide's original
next step (qualify actual capture state, then bind it to the pinned declaration)
remains a separate integration decision, not an alternative to the current worker,
sentinel, resource owner or human artistic review. See the current continuation
in [critic observations](../../critic-observations/README.md).
