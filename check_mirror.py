#!/usr/bin/env python3
"""Prove the browser's local rule-mirror still matches the contract.

index.html re-implements the opening validation of `create_market` so a reader
gets the refusal instantly instead of paying gas to be told nothing. That is
only honest while the two agree, and a mirror that drifts is worse than no
mirror at all — it would quote a rule the contract no longer has.

This checks three things:

  1. every constant the mirror transcribes still holds the same value in
     settled.py;
  2. the mirror's checks fire in the same ORDER as the contract's, so the first
     sentence shown is the first sentence the contract would raise;
  3. every sentence the mirror can return still exists verbatim in the contract.

Run:  python3 contracts/check_mirror.py
"""

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
PY = (ROOT / "contracts" / "settled.py").read_text(encoding="utf-8")

problems = []


def contract_constants():
    """Constants as the contract actually defines them."""
    out = {}
    tree = ast.parse(PY)
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                pass
    return out


C = contract_constants()

# --- 1. constants -------------------------------------------------------
js_hosts = re.search(r"const OPAQUE_HOSTS = \[(.*?)\];", HTML, re.S)
if not js_hosts:
    problems.append("OPAQUE_HOSTS not found in index.html")
else:
    mirrored = tuple(re.findall(r"'([^']+)'", js_hosts.group(1)))
    if mirrored != tuple(C.get("_OPAQUE_HOSTS", ())):
        problems.append(
            f"shortener list differs\n     contract: {C.get('_OPAQUE_HOSTS')}\n"
            f"     mirror:   {mirrored}"
        )

for js_name, py_name in [
    ("MAX_ID_CHARS", "_MAX_ID_CHARS"),
    ("MAX_URL_CHARS", "_MAX_URL_CHARS"),
    ("MAX_EMBARGO", "_MAX_EMBARGO"),
]:
    m = re.search(rf"const {js_name} = (\d+);", HTML)
    if not m:
        problems.append(f"{js_name} not found in index.html")
    elif int(m.group(1)) != C.get(py_name):
        problems.append(f"{js_name} is {m.group(1)}, contract {py_name} is {C.get(py_name)}")

# --- 2 & 3. sentences, and the order they fire in -----------------------
mirror = re.search(r"function localRefusal\(fn, args\) \{(.*?)\n\}", HTML, re.S)
if not mirror:
    problems.append("localRefusal() not found in index.html")
    mirror_msgs = []
else:
    mirror_msgs = re.findall(r"return '([^']+)';", mirror.group(1))
    mirror_msgs = [m for m in mirror_msgs if m]

for msg in mirror_msgs:
    if f'"{msg}"' not in PY:
        problems.append(f"mirror returns a sentence the contract does not raise: {msg!r}")

# The contract's order, taken from the body of create_market itself.
create = next(
    (n for n in ast.walk(ast.parse(PY))
     if isinstance(n, ast.FunctionDef) and n.name == "create_market"),
    None,
)
if create is None:
    problems.append("create_market not found in settled.py")
else:
    contract_order = []
    for n in ast.walk(create):
        if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call) and n.exc.args:
            a = n.exc.args[0]
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                contract_order.append((a.lineno, a.value))
    contract_order = [m for _, m in sorted(contract_order)]

    rank = {m: i for i, m in enumerate(contract_order)}
    ranked = [rank[m] for m in mirror_msgs if m in rank]
    if ranked != sorted(ranked):
        problems.append(
            "mirror checks fire in a different order than the contract's:\n"
            f"     contract: {[contract_order[i] for i in sorted(ranked)]}\n"
            f"     mirror:   {[m for m in mirror_msgs if m in rank]}"
        )

# --- report -------------------------------------------------------------
if problems:
    print("MIRROR HAS DRIFTED\n")
    for p in problems:
        print(f"  - {p}")
    sys.exit(1)

print(f"mirror matches the contract — {len(mirror_msgs)} sentences, in the contract's own order")
