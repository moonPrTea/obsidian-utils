import unittest
from pathlib import Path
from unittest.mock import patch

from obsidian_utils.classifier import TagClassifier
from obsidian_utils.evaluation import evaluate, split_examples
from obsidian_utils.vault import Note


def create_examples() -> list[Note]:
    categories = {
        'work': 'server deployment configuration for a work application',
        'study': 'textbook lecture exam practice exercise',
    }

    return [
        Note(Path(f'{tag}-{index}.md'), f'{text} token{tag}{index}', {tag}, f'{text} token{tag}{index}')
        for tag, text in categories.items()
        for index in range(20)
    ]


class EvaluationTests(unittest.TestCase):
    def test_holdout_vocabulary_and_repeatability(self):
        notes = create_examples()
        training_samples, testing_samples = split_examples(notes)
        classifier = TagClassifier()

        with patch('obsidian_utils.evaluation.TagClassifier', return_value=classifier):
            report = evaluate(notes, ['work', 'study'], threshold=0.5)

        for note in testing_samples:
            self.assertNotIn(note.text.split()[-1], classifier.vectorizer.vocabulary_)
        for note in training_samples:
            self.assertIn(note.text.split()[-1], classifier.vectorizer.vocabulary_)

        self.assertEqual(report['train_size'], 30)
        self.assertEqual(report['test_size'], 10)
        self.assertEqual(report, evaluate(notes, ['work', 'study'], threshold=0.5))
        self.assertEqual({row['file'] for row in report['results']}, {str(note.path) for note in testing_samples})

    def test_duplicates_and_unlabelled_notes_are_excluded(self):
        notes = create_examples()
        original = notes[0]
        duplicate_body = original.body.upper().replace(' ', '  ')
        notes.append(Note(Path('copy.md'), 'Different title', original.tags, duplicate_body))
        notes.append(Note(Path('new.md'), 'Text without tags', set(), 'Text without tags'))

        training_samples, testing_samples = split_examples(notes)
        training_bodies = {' '.join(note.body.casefold().split()) for note in training_samples}
        testing_bodies = {' '.join(note.body.casefold().split()) for note in testing_samples}

        self.assertEqual(len(training_samples) + len(testing_samples), 40)
        self.assertFalse(training_bodies & testing_bodies)

    def test_metrics_for_errors_multiple_labels_and_abstention(self):
        actual_tags = [{'work'}, {'study'}, {'work', 'study'}, {'work'}]
        testing_samples = [
            Note(Path(f'check-{index}.md'), f'Test sample text {index}', tags, f'Test sample text {index}')
            for index, tags in enumerate(actual_tags)
        ]
        training_samples = create_examples()
        classifier = unittest.mock.Mock()
        classifier.fit.return_value = classifier
        classifier.suggest.side_effect = [['work'], ['work'], ['study'], []]

        with patch('obsidian_utils.evaluation.split_examples', return_value=(training_samples, testing_samples)), \
                patch('obsidian_utils.evaluation.TagClassifier', return_value=classifier):
            report = evaluate(training_samples + testing_samples, ['work', 'study'])

        classifier.fit.assert_called_once_with(training_samples, ['study', 'work'])
        self.assertAlmostEqual(report['per_tag']['work']['precision'], 0.5)
        self.assertAlmostEqual(report['per_tag']['work']['recall'], 1 / 3)
        self.assertAlmostEqual(report['per_tag']['work']['f1'], 0.4)
        self.assertAlmostEqual(report['per_tag']['study']['precision'], 1.0)
        self.assertAlmostEqual(report['per_tag']['study']['recall'], 0.5)
        self.assertAlmostEqual(report['per_tag']['study']['f1'], 2 / 3)
        self.assertEqual(report['coverage'], 0.75)
        self.assertEqual(report['exact_match'], 0.25)
        self.assertEqual(report['results'][-1]['predicted_tags'], [])

    def test_small_dataset_invalid_threshold_and_empty_tags(self):
        with self.assertRaisesRegex(ValueError, 'distinct labelled'):
            evaluate(create_examples()[:4], ['work', 'study'])

        for threshold in (0, 1, float('nan')):
            with self.subTest(threshold=threshold), self.assertRaisesRegex(ValueError, 'Threshold'):
                evaluate(create_examples(), ['work', 'study'], threshold)

        with self.assertRaisesRegex(ValueError, 'empty'):
            evaluate(create_examples(), [])

    def test_missing_test_examples_and_unknown_tags(self):
        notes = create_examples()
        with patch('obsidian_utils.evaluation.split_examples', return_value=(notes, notes[:2])):
            with self.assertRaisesRegex(ValueError, 'test split'):
                evaluate(notes, ['work', 'study'])

        with patch('obsidian_utils.evaluation.split_examples', return_value=(notes[:20], notes[20:])):
            with self.assertRaisesRegex(ValueError, 'outside the dictionary'):
                evaluate(notes, ['work'])
