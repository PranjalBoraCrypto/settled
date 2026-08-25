#!/usr/bin/env python3
"""Pre-deploy check: every name a contract loads must resolve IN ITS OWN SCOPE.

This exists because the same defect reached three separate audit rounds, in three
different functions. A name that does not resolve raises NameError; inside the
broad `except Exception` that every non-deterministic block needs for network and
model faults, that exception is swallowed. It is swallowed identically on every
validator, so the nodes agree, consensus passes, and the feature reports a
clean-looking outage forever. Invisible to reading, to the linter, and to any
test that does not exercise that branch.

Scope awareness is the whole point. The first version of this file pooled every
assignment in the module into one flat set, and so a name bound inside resolve()
counted as resolving a load inside snapshot() — which is exactly the bug that
shipped. It passed a file whose snapshot() was dead.
"""
import ast, builtins, sys

GENLAYER = {
    'gl', 'Address', 'allow_storage', 'Array', 'DynArray', 'Keccak256', 'TreeMap',
    'bigint', 'u8', 'u16', 'u24', 'u32', 'u64', 'u128', 'u160', 'u256',
    'i8', 'i16', 'i32', 'i64', 'i128', 'i256',
}
BUILTIN = set(dir(builtins)) | {'__name__', '__doc__'}


def _targets(node):
    """Names bound by one statement, without descending into nested scopes."""
    out = set()
    def walk(t):
        if isinstance(t, ast.Name):
            out.add(t.id)
        elif isinstance(t, (ast.Tuple, ast.List)):
            for e in t.elts:
                walk(e)
        elif isinstance(t, ast.Starred):
            walk(t.value)
    if isinstance(node, ast.Assign):
        for t in node.targets:
            walk(t)
    elif isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.For, ast.AsyncFor)):
        walk(node.target)
    elif isinstance(node, ast.NamedExpr):
        walk(node.target)
    elif isinstance(node, (ast.With, ast.AsyncWith)):
        for item in node.items:
            if item.optional_vars is not None:
                walk(item.optional_vars)
    elif isinstance(node, ast.ExceptHandler) and node.name:
        out.add(node.name)
    elif isinstance(node, ast.Import):
        out |= {a.asname or a.name.split('.')[0] for a in node.names}
    elif isinstance(node, ast.ImportFrom):
        out |= {a.asname or a.name for a in node.names}
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        out.add(node.name)
    return out


def _local_binds(scope_node):
    """Every name bound directly in this scope, not in nested function bodies."""
    out = set()
    if isinstance(scope_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        a = scope_node.args
        for arg in [*a.posonlyargs, *a.args, *a.kwonlyargs]:
            out.add(arg.arg)
        if a.vararg:
            out.add(a.vararg.arg)
        if a.kwarg:
            out.add(a.kwarg.arg)
    bodies = scope_node.body if isinstance(scope_node, ast.Module) else scope_node.body
    stack = list(bodies)
    while stack:
        n = stack.pop()
        out |= _targets(n)
        # do not descend into a nested function/class body — that is its own scope
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for child in ast.iter_child_nodes(n):
            stack.append(child)
    return out


def _comp_binds(node):
    out = set()
    for gen in getattr(node, 'generators', []):
        t = gen.target
        for sub in ast.walk(t):
            if isinstance(sub, ast.Name):
                out.add(sub.id)
    return out


def check(path):
    tree = ast.parse(open(path).read(), path)
    module_scope = _local_binds(tree) | GENLAYER | BUILTIN
    problems = {}

    def visit(node, enclosing):
        """enclosing = names visible here from outer scopes."""
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            visible = enclosing | _local_binds(node)
        elif isinstance(node, ast.ClassDef):
            visible = enclosing | _local_binds(node)
        else:
            visible = enclosing

        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                visit(child, visible)
            else:
                stack = [(child, visible)]
                while stack:
                    n, vis = stack.pop()
                    if isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                        vis = vis | _comp_binds(n)
                    if isinstance(n, ast.Lambda):
                        vis = vis | {a.arg for a in [*n.args.posonlyargs, *n.args.args, *n.args.kwonlyargs]}
                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in vis:
                        problems.setdefault(n.id, n.lineno)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        visit(n, vis)
                        continue
                    for c in ast.iter_child_nodes(n):
                        stack.append((c, vis))

    visit(tree, module_scope)
    return problems


bad = 0
# Default to the two contracts, found next to this script or one level up, so a
# reader can run `python3 check_names.py` with no arguments and get an answer.
# check_mirror.py shipped once assuming a layout that did not exist in the
# repository, and crashed for anyone who tried it; the same mistake is cheap to
# avoid twice.
def _default_paths():
    import pathlib
    here = pathlib.Path(__file__).resolve().parent
    found = []
    for name in ("settled.py", "payout.py"):
        for base in (here, here.parent, pathlib.Path.cwd()):
            for cand in (base / name, base / "contracts" / name):
                if cand.is_file():
                    found.append(str(cand))
                    break
            else:
                continue
            break
    if not found:
        sys.exit("could not find settled.py or payout.py. Pass them as arguments, "
                 "or run this from the directory that holds them.")
    return found


targets = sys.argv[1:] or _default_paths()

for path in targets:
    problems = check(path)
    if problems:
        bad = 1
        print(f"FAIL {path}")
        for name, line in sorted(problems.items(), key=lambda kv: kv[1]):
            print(f"     line {line}: '{name}' does not resolve in its scope")
    else:
        print(f"ok   {path}: every name resolves in its own scope")
sys.exit(bad)
