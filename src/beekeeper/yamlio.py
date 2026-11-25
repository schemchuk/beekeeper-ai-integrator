"""YAML loading that remembers where each mapping and sequence started (1-based line)."""

from pathlib import Path

import yaml


class Mapping(dict):
    line: int = 0


class Sequence(list):
    line: int = 0


class _Loader(yaml.SafeLoader):
    pass


def _mapping(loader: _Loader, node: yaml.MappingNode) -> Mapping:
    out = Mapping(loader.construct_mapping(node, deep=True))
    out.line = node.start_mark.line + 1
    return out


def _sequence(loader: _Loader, node: yaml.SequenceNode) -> Sequence:
    out = Sequence(loader.construct_sequence(node, deep=True))
    out.line = node.start_mark.line + 1
    return out


_Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)
_Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_SEQUENCE_TAG, _sequence)


def load(path: Path) -> object:
    with path.open(encoding="utf-8") as f:
        return yaml.load(f, Loader=_Loader)


def line_of(value: object) -> int:
    return getattr(value, "line", 0)
