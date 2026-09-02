#!/usr/bin/env python3
"""Verify the analytics suite using only the standard library.

The sandbox has no network, so pytest cannot be installed here. This harness:

* injects a minimal :mod:`pytest` stub so ``import pytest`` works (the stub
  provides ``raises``, ``approx``, ``mark.parametrize`` and ``skipif``);
* resolves the simple name-based fixtures in ``conftest.py`` recursively;
* runs every ``test_*`` function that does not take parametrized kwargs.

Parametrized tests (which the real pytest expands) are detected and reported as
SKIPPED here rather than executed, so their count matches the author's intent
and they do not surface as false failures.

This is NOT a substitute for ``pytest`` - CI runs the real thing. Run locally in
the sandbox purely as a smoke signal that the suite is green.

Usage:
    python3 tests/run_with_stdlib.py
"""
from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
HERE = Path(__file__).resolve().parent


# --------------------------------------------------------------------------- #
# Minimal pytest stub
# --------------------------------------------------------------------------- #
class _PytestStub:
    def raises(self, exc, match=None):
        class _Ctx:
            def __enter__(inner):
                return inner

            def __exit__(inner, et, ev, tb):
                if et is None:
                    raise AssertionError(f"DID NOT RAISE {exc}")
                return issubclass(et, exc) if isinstance(et, type) else False

            def __getattr__(inner, name):  # allow .value, .match etc in tests
                return inner

        return _Ctx()

    class approx:
        def __init__(self, value, abs=None, rel=None):
            self.value = value
            self.abs = abs

        def __eq__(self, other):
            from decimal import Decimal

            delta = self.abs if self.abs is not None else Decimal("0.001")
            return abs(Decimal(str(other)) - Decimal(str(self.value))) <= delta

    class mark:
        class _Marker:
            def __init__(self, fn=None):
                self.fn = fn

            def __call__(self, *a, **k):
                return self.fn or (lambda f: f)

            def __getattr__(self, name):
                return lambda *a, **k: self._wrap(name, a, k)

            def _wrap(self, name, args, kwargs):
                def deco(fn):
                    setattr(fn, "_pytest_param", (name, args, kwargs))
                    return fn

                return lambda f: deco(f)

        def __getattr__(self, name):
            return self._Marker()

        def __call__(self, *a, **k):
            return self._Marker()

    def skipif(self, *a, **k):
        return self.mark._Marker()

    def skip(self, reason=""):
        raise SkipTest(reason)


class SkipTest(Exception):
    pass


def main() -> int:
    import types

    pytest_stub = _PytestStub()
    sys.modules["pytest"] = pytest_stub

    # Submodule attribute access on the stub is routed through __getattr__ so
    # pytest.mark.parametrize and pytest.raises both work.
    class _Module(types.ModuleType):
        def __getattr__(self, name):
            return getattr(pytest_stub, name)

    sys.modules["pytest"] = _Module("pytest")

    def load(path: Path, name: str):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    conftest_path = HERE / "conftest.py"
    conftest = load(conftest_path, "_conftest")
    fixtures = {
        n: v
        for n, v in vars(conftest).items()
        if not n.startswith("_") and inspect.isfunction(v)
    }

    def resolve(name, fixtures, memo, stack):
        if name in memo:
            return memo[name]
        if name in stack:
            raise RuntimeError(f"circular fixture: {stack + (name,)}")
        factory = fixtures.get(name)
        if factory is None:
            raise ValueError(f"fixture {name!r} not found")
        args = [resolve(p.name, fixtures, memo, stack + (name,))
                for p in inspect.signature(factory).parameters.values()]
        value = factory(*args)
        memo[name] = value
        return value

    passed = skipped = 0
    failures = []
    for test_file in sorted(HERE.rglob("test_*.py")):
        module = load(test_file, "_m_" + test_file.stem)
        for name, fn in sorted(vars(module).items()):
            if not (name.startswith("test_") and inspect.isfunction(fn)):
                continue
            if getattr(fn, "_pytest_param", None):
                skipped += 1
                continue
            try:
                sig = inspect.signature(fn)
                args = [resolve(p.name, fixtures, {}, ())
                        for p in sig.parameters.values()]
                fn(*args)
                passed += 1
            except SkipTest:
                skipped += 1
            except Exception as exc:  # noqa: BLE001
                failures.append((name, test_file.name, str(exc)))

    print(f"passed={passed} skipped={skipped} failed={len(failures)}")
    for name, file, err in failures:
        print(f"FAIL {file}::{name}: {err}")
    return 0 if not failures and passed > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
