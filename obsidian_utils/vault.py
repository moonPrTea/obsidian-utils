from pathlib import Path
from typing import Iterable
from urllib.parse import unquote

import yaml

from .constants import (
    CONTENT_WORD_PATTERN, DEFAULT_CONFIG_FILE, HEADING_PATTERN,
    MIN_CONTENT_WORDS, TABLE_SEPARATOR_PATTERN,
)
from .markdown import clean_text, link_targets, split_note


class Note:
    def __init__(self, path: Path, text: str, tags: set[str], body: str):
        self.path = path
        self.text = text
        self.tags = tags
        self.body = body


def resolve_note(vault_root: Path, source_path: Path, target: str, note_paths: list[Path]) -> Path:
    target = unquote(target.split('#', 1)[0]).replace('\\', '/')
    if not target:
        raise ValueError('Empty category link')

    relative_path = Path(target)
    if relative_path.suffix != '.md':
        relative_path = Path(str(relative_path) + '.md')

    for candidate_path in (source_path.parent / relative_path, vault_root / relative_path):
        resolved_path = candidate_path.resolve()
        if not resolved_path.is_relative_to(vault_root):
            raise ValueError(f'Link points outside the vault: {target}')

        if resolved_path in note_paths:
            return resolved_path

    matching_paths = []
    if '/' not in target:
        matching_paths = [note_path for note_path in note_paths if note_path.name == relative_path.name]

    if len(matching_paths) != 1:
        raise ValueError(f'Missing or ambiguous link: {target}')

    return matching_paths[0]


def load_vault(directory, config: str = DEFAULT_CONFIG_FILE, exclude: Iterable[str] = ()):
    vault_root = Path(directory).expanduser().resolve()
    if not vault_root.is_dir():
        raise ValueError(f'Vault directory does not exist: {vault_root}')

    note_paths = sorted(
        note_path for note_path in vault_root.rglob('*.md')
        if not any(part.startswith('.') for part in note_path.relative_to(vault_root).parts)
        and not any(note_path.relative_to(vault_root).match(pattern) for pattern in exclude)
        and note_path.resolve().is_relative_to(vault_root)
        and not note_path.is_symlink()
    )
    index_path = resolve_note(vault_root, vault_root / '_root.md', config, note_paths)

    def read_note(note_path: Path, keep_inline: bool = False) -> tuple[str, set[str]]:
        try:
            return split_note(note_path.read_text(encoding='utf-8-sig'), keep_inline=keep_inline)
        except (ValueError, yaml.YAMLError) as error:
            raise ValueError(f'{note_path.relative_to(vault_root)}: {error}') from error

    categories = {}
    index_text, _ = read_note(index_path, keep_inline=True)

    for line in index_text.splitlines():
        if '|' not in line:
            continue

        table_cells = TABLE_SEPARATOR_PATTERN.split(line.strip().strip('|'))
        if len(table_cells) < 2:
            continue

        category_targets = link_targets(table_cells[0].replace('\\|', '|'))
        if not category_targets:
            continue

        if len(category_targets) != 1:
            raise ValueError('The Code cell must contain exactly one link')

        category_path = resolve_note(vault_root, index_path, category_targets[0], note_paths)
        _, category_tags = read_note(category_path)
        if len(category_tags) != 1:
            raise ValueError(f'{category_path.name}: expected exactly one category tag')

        category_tag = next(iter(category_tags))
        if category_tag in categories:
            raise ValueError(f'Tag #{category_tag} appears more than once in the index')

        categories[category_tag] = {
            'path': category_path,
            'description': table_cells[1].strip(' `'),
        }

    if not categories:
        raise ValueError('The index contains no table rows with category links')

    service_paths = {index_path} | {category['path'] for category in categories.values()}
    category_names = {service_path.stem for service_path in service_paths}
    category_names.update(
        service_path.relative_to(vault_root).with_suffix('').as_posix()
        for service_path in service_paths
    )
    notes = []
    skipped_paths = []

    for note_path in note_paths:
        if note_path in service_paths:
            continue

        note_text, note_tags = read_note(note_path)
        source_parent = note_path.parent.relative_to(vault_root).as_posix()
        note_body = clean_text(note_text, category_names, source_parent)
        content = HEADING_PATTERN.sub('', note_body)
        if len(CONTENT_WORD_PATTERN.findall(content)) < MIN_CONTENT_WORDS:
            skipped_paths.append(str(note_path.relative_to(vault_root)))
            continue

        notes.append(Note(
            path=note_path,
            text=note_path.stem + '\n' + note_body,
            tags=note_tags & categories.keys(),
            body=note_body,
        ))

    return vault_root, categories, notes, skipped_paths
