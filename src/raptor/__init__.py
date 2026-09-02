"""Namespace package root for the ``raptor`` project.

Declared as a PEP 420 implicit namespace package so the backend (Issue #2) can
add ``raptor.api`` and ``raptor.agents`` in the same tree without either branch
touching this file. That is the mechanical reason the three workstreams merge
without a rewrite.
"""
