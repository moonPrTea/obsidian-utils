import posixpath
from urllib.parse import unquote

import yaml

from .constants import (
    CODE_FENCE_PATTERN, COMMENT_PATTERN, INLINE_CODE_PATTERN,
    MARKDOWN_LINK_PATTERN, TAG_PATTERN, TAG_SEPARATOR_PATTERN,
    URL_PATTERN, WIKI_LINK_PATTERN,
)


def visible_text(text: str, keep_inline: bool = False) -> str:
    text = COMMENT_PATTERN.sub('', text)
    visible_lines = []
    active_fence = None

    for line in text.splitlines():
        fence_match = CODE_FENCE_PATTERN.match(line)
        if fence_match:
            fence_marker, fence_suffix = fence_match.groups()
            if active_fence is None:
                active_fence = fence_marker
            elif (
                fence_marker[0] == active_fence[0]
                and len(fence_marker) >= len(active_fence)
                and not fence_suffix.strip()
            ):
                active_fence = None
            continue

        if active_fence is None and not line.startswith(('    ', '\t')):
            visible_lines.append(line)

    text = '\n'.join(visible_lines)
    if keep_inline:
        return text

    return INLINE_CODE_PATTERN.sub('', text)


def split_note(raw_text: str, keep_inline: bool = False) -> tuple[str, set[str]]:
    raw_text = raw_text.lstrip('\ufeff')
    metadata = {}
    note_lines = raw_text.splitlines()

    if note_lines and note_lines[0].strip() == '---':
        frontmatter_end = next(
            (index for index in range(1, len(note_lines)) if note_lines[index].strip() == '---'),
            None,
        )
        if frontmatter_end is None:
            raise ValueError('Unclosed YAML frontmatter')

        metadata = yaml.safe_load('\n'.join(note_lines[1:frontmatter_end])) or {}
        if not isinstance(metadata, dict):
            raise ValueError('YAML frontmatter must be a mapping')

        raw_text = '\n'.join(note_lines[frontmatter_end + 1:])

    metadata_tags = metadata.get('tags', []) or []
    if isinstance(metadata_tags, str):
        metadata_tags = TAG_SEPARATOR_PATTERN.split(metadata_tags)

    if not isinstance(metadata_tags, list) or any(not isinstance(tag, str) for tag in metadata_tags):
        raise ValueError('The tags property must be a string or a list of strings')

    tags = {tag.lstrip('#').casefold() for tag in metadata_tags if tag}
    text = visible_text(raw_text)
    tag_text = MARKDOWN_LINK_PATTERN.sub('', WIKI_LINK_PATTERN.sub('', text))
    tag_text = URL_PATTERN.sub('', tag_text)
    tags.update(tag.casefold() for tag in TAG_PATTERN.findall(tag_text))

    if keep_inline:
        text = visible_text(raw_text, keep_inline=True)

    return text, tags


def link_targets(text: str) -> list[str]:
    wiki_targets = [match.group(1) for match in WIKI_LINK_PATTERN.finditer(text)]
    markdown_targets = [match.group(2) for match in MARKDOWN_LINK_PATTERN.finditer(text)]

    return wiki_targets + markdown_targets


def clean_text(text: str, category_names: set[str], source_parent: str = '') -> str:
    def normalize_target(target: str) -> str:
        return unquote(target.split('#', 1)[0]).replace('\\', '/').removesuffix('.md')

    def is_category(target: str) -> bool:
        target = normalize_target(target)
        candidate_paths = {
            posixpath.normpath(target),
            posixpath.normpath(posixpath.join(source_parent, target)),
        }

        return bool(candidate_paths & category_names)

    def wiki_label(link_match) -> str:
        target = link_match.group(1)
        if is_category(target):
            return ''

        return link_match.group(2) or normalize_target(target)

    def markdown_label(link_match) -> str:
        if is_category(link_match.group(2)):
            return ''

        return link_match.group(1)

    text = WIKI_LINK_PATTERN.sub(wiki_label, text)
    text = MARKDOWN_LINK_PATTERN.sub(markdown_label, text)

    return TAG_PATTERN.sub('', text).strip()
