import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from obsidian_utils.__main__ import main


def populate_vault(vault_root: Path):
    (vault_root / 'config-f.md').write_text('| [[011-1]] | Work |\n| [[011-3]] | Study |', encoding='utf-8')
    examples = [
        ('011-1', 'work', 'server deployment configuration for a work application'),
        ('011-3', 'study', 'textbook lecture exam practice exercise'),
    ]
    for category, tag, text in examples:
        (vault_root / f'{category}.md').write_text(f'#{tag}', encoding='utf-8')
        for index in range(20):
            (vault_root / f'{tag}-{index}.md').write_text(f'#{tag}\n{text} example{index}', encoding='utf-8')

    (vault_root / 'new.md').write_text(examples[0][2], encoding='utf-8')
    (vault_root / 'unknown.md').write_text('quasar nebula galaxy cosmos asteroid', encoding='utf-8')
    (vault_root / 'short.md').write_text('Short text', encoding='utf-8')


class CliTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.vault_root = Path(self.directory.name)
        populate_vault(self.vault_root)

    def run_command(self, command, *arguments):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main([command, str(self.vault_root), *arguments]), 0)
        return json.loads(output.getvalue())

    def test_commands_preserve_notes_and_return_predictions(self):
        original = {path.name: path.read_bytes() for path in self.vault_root.iterdir()}
        inspection = self.run_command('inspect')
        self.assertEqual(inspection['usable_notes'], 42)
        self.assertEqual(inspection['unlabelled'], 2)
        self.assertEqual(inspection['categories']['work']['examples'], 20)
        self.assertEqual(inspection['categories']['work']['file'], '011-1.md')
        self.assertEqual(inspection['skipped_short'], ['short.md'])

        report = self.run_command('suggest', '--threshold', '0.5')
        self.assertEqual(report['training_notes'], 40)
        suggestions = {item['file']: item for item in report['suggestions']}
        self.assertEqual(set(suggestions), {'new.md', 'unknown.md'})
        self.assertEqual(suggestions['new.md']['tags'], ['work'])
        self.assertTrue(suggestions['new.md']['needs_review'])
        self.assertFalse(suggestions['new.md']['abstained'])
        self.assertEqual(suggestions['unknown.md']['tags'], [])
        self.assertTrue(suggestions['unknown.md']['abstained'])
        self.assertTrue(all(score == 0 for score in suggestions['unknown.md']['scores'].values()))

        evaluation = self.run_command('evaluate', '--threshold', '0.5')
        self.assertEqual((evaluation['train_size'], evaluation['test_size']), (30, 10))
        self.assertEqual(set(evaluation['per_tag']), {'work', 'study'})
        self.assertTrue(all(not Path(item['file']).is_absolute() for item in evaluation['results']))
        self.assertEqual(original, {path.name: path.read_bytes() for path in self.vault_root.iterdir()})

    def test_custom_index_and_repeated_exclusions(self):
        (self.vault_root / 'config-f.md').rename(self.vault_root / 'index.md')
        report = self.run_command('inspect', '--config', 'index.md', '--exclude', 'new.md', '--exclude', 'unknown.md')
        self.assertEqual(report['unlabelled'], 0)
        self.assertEqual(report['usable_notes'], 40)

    def test_no_pending_notes_needs_no_training(self):
        for path in self.vault_root.glob('*.md'):
            if path.name not in {'config-f.md', '011-1.md', '011-3.md', 'work-0.md'}:
                path.unlink()
        report = self.run_command('suggest')
        self.assertEqual(report['suggestions'], [])
        self.assertEqual(report['training_notes'], 1)

    def test_errors_go_to_stderr_without_json(self):
        for command in ('inspect', 'suggest', 'evaluate'):
            output, errors = io.StringIO(), io.StringIO()
            with self.subTest(command=command), redirect_stdout(output), redirect_stderr(errors):
                self.assertEqual(main([command, str(self.vault_root / 'missing')]), 2)
            self.assertEqual(output.getvalue(), '')
            self.assertIn('Error: Vault directory does not exist', errors.getvalue())

    def test_invalid_threshold_is_rejected(self):
        for threshold in ('0', '1', 'nan', 'inf'):
            with self.subTest(threshold=threshold), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    main(['suggest', str(self.vault_root), '--threshold', threshold])
                self.assertEqual(error.exception.code, 2)

    def test_json_supports_unicode_with_legacy_stdout_encoding(self):
        description = '\u0420\u0430\u0431\u043e\u0442\u0430 \U0001f4da'
        index = self.vault_root / 'config-f.md'
        index.write_text(index.read_text(encoding='utf-8').replace('Work', description), encoding='utf-8')
        buffer = io.BytesIO()
        output = io.TextIOWrapper(buffer, encoding='cp1251', write_through=True)
        with redirect_stdout(output):
            self.assertEqual(main(['inspect', str(self.vault_root)]), 0)
        report = json.loads(buffer.getvalue().decode('cp1251'))
        self.assertEqual(report['categories']['work']['description'], description)
        output.close()

    def test_module_entrypoint_and_help(self):
        project_root = Path(__file__).resolve().parents[1]
        for arguments in (['--help'], ['inspect', str(self.vault_root)]):
            process = subprocess.run(
                [sys.executable, '-B', '-m', 'obsidian_utils', *arguments],
                cwd=project_root, capture_output=True, text=True,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(process.stderr, '')
            if arguments == ['--help']:
                self.assertIn('--exclude', process.stdout)
            else:
                self.assertEqual(json.loads(process.stdout)['usable_notes'], 42)
