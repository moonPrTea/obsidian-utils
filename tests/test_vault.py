import tempfile
import unittest
from pathlib import Path

from obsidian_utils.vault import load_vault


class VaultTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.vault_root = Path(self.temporary_directory.name)
        self.write_note(
            'config-f.md',
            '#config\n|Code|Description|\n|---|---|\n'
            '|[[011-1]]|work|\n|[011-3](011-3.md)|study|',
        )
        self.write_note('011-1.md', '#work_info\n[[AD project]]')
        self.write_note('011-3.md', '#study')

    def write_note(self, relative_path: str, text: str):
        note_path = self.vault_root / relative_path
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(text, encoding='utf-8')

    def test_read_only_and_service_exclusion(self):
        self.write_note('AD project.md', '#work_info\nConfigure a work server to handle incoming requests.')
        self.write_note('empty.md', '# Empty\n#work_info')
        self.write_note('new.md', '#other\nStudy graph pathfinding algorithms independently with practical exercises.')
        self.write_note('.trash/deleted.md', '#study\nThis note was deleted and must not be included.')
        original_contents = {note_path: note_path.read_bytes() for note_path in self.vault_root.rglob('*.md')}

        _, categories, notes, skipped_paths = load_vault(self.vault_root)
        new_note_tags = next(note.tags for note in notes if note.path.name == 'new.md')
        current_contents = {note_path: note_path.read_bytes() for note_path in self.vault_root.rglob('*.md')}

        self.assertEqual(set(categories), {'work_info', 'study'})
        self.assertEqual({note.path.name for note in notes}, {'AD project.md', 'new.md'})
        self.assertEqual(new_note_tags, set())
        self.assertEqual(skipped_paths, ['empty.md'])
        self.assertEqual(original_contents, current_contents)

    def test_ambiguous_link_fails(self):
        (self.vault_root / '011-1.md').unlink()
        self.write_note('a/011-1.md', '#work_info')
        self.write_note('b/011-1.md', '#work_info')

        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            load_vault(self.vault_root)

    def test_outside_link_is_rejected(self):
        self.write_note('config-f.md', '|Code|Description|\n|[[../outside]]|bad|')

        with self.assertRaisesRegex(ValueError, 'outside the vault'):
            load_vault(self.vault_root)

    def test_multiple_category_tags_are_not_guessed(self):
        self.write_note('011-1.md', '#work_info #extra')

        with self.assertRaisesRegex(ValueError, 'exactly one'):
            load_vault(self.vault_root)

    def test_aliases_in_table_and_excluded_templates(self):
        self.write_note('config-f.md', r'|[[011-1\|Work]]|`about work projects, just documentation`|')
        self.write_note('templates/base.md', '#work_info\nTemplate text must not be included in the examples.')

        _, categories, notes, _ = load_vault(self.vault_root, exclude=['templates/*'])

        self.assertEqual(set(categories), {'work_info'})
        self.assertEqual(categories['work_info']['description'], 'about work projects, just documentation')
        self.assertEqual(notes, [])

    def test_nested_index_and_explicit_note_tags(self):
        self.write_note('config-f.md', '|[[011-1]]|work|')
        self.write_note('011-1.md', '---\ntags: [work_info]\n---\n[[projects/new]]')
        self.write_note('indexes/config-f.md', '|[[../011%2D1]]|`work`|')
        self.write_note('projects/new.md', 'The bot checks work services and reports any errors.\n'
                        '[[../011-1|work_info]]')

        _, categories, notes, _ = load_vault(self.vault_root, config='indexes/config-f.md')
        project_note = next(note for note in notes if note.path.name == 'new.md')

        self.assertEqual(set(categories), {'work_info'})
        self.assertEqual(project_note.tags, set())
        self.assertNotIn('work_info', project_note.body)

    def test_table_without_outer_pipes(self):
        self.write_note('config-f.md', 'Code | Description\n--- | ---\n[[011-1]] | `work`')

        _, categories, _, _ = load_vault(self.vault_root)

        self.assertEqual(set(categories), {'work_info'})
        self.assertEqual(categories['work_info']['description'], 'work')

    def test_symlink_outside_vault_is_ignored(self):
        with tempfile.TemporaryDirectory() as outside_directory:
            outside_note = Path(outside_directory) / 'private.md'
            outside_note.write_text('#work_info\nA note outside the vault must not be included.', encoding='utf-8')
            (self.vault_root / 'external.md').symlink_to(outside_note)

            _, _, notes, _ = load_vault(self.vault_root)

            self.assertEqual(notes, [])
