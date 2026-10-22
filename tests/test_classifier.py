import unittest
from pathlib import Path

from obsidian_utils.classifier import TagClassifier, training_notes
from obsidian_utils.vault import Note


def create_examples() -> list[Note]:
    categories = {
        'work_info': [
            'server deployment configuration for a work application',
            'server deployment setup for a work environment',
            'server deployment monitoring for work services',
            'server deployment application error logging',
        ],
        'study': [
            'textbook lecture exam search algorithms',
            'textbook lecture exam data structures',
            'textbook lecture exam graph theory',
            'textbook lecture exam sorting methods',
        ],
    }

    return [
        Note(Path(f'{tag}-{index}.md'), text, {tag}, text)
        for tag, texts in categories.items()
        for index, text in enumerate(texts)
    ]


class ClassifierTests(unittest.TestCase):
    def test_topics_and_unknown_vocabulary(self):
        classifier = TagClassifier().fit(create_examples(), ['work_info', 'study'])

        self.assertEqual(classifier.suggest('server deployment', threshold=0.5), ['work_info'])
        self.assertEqual(classifier.suggest('textbook lecture exam', threshold=0.5), ['study'])
        self.assertEqual(classifier.suggest('qzxvnotaword'), [])
        self.assertEqual(classifier.suggest(''), [])

    def test_duplicates_and_unlabelled_notes(self):
        original = create_examples()[0]
        duplicate = Note(Path('copy.md'), 'Different title\n' + original.text, original.tags, original.body)
        unlabelled = Note(Path('new.md'), original.text, set(), original.body)

        self.assertEqual(training_notes([original, duplicate, unlabelled]), [original])

        duplicate.tags = {'study'}
        with self.assertRaisesRegex(ValueError, 'Conflicting tags'):
            training_notes([original, duplicate])

    def test_insufficient_examples_and_unknown_tags(self):
        with self.assertRaisesRegex(ValueError, 'positive'):
            TagClassifier().fit(create_examples()[:2], ['work_info'])

        with self.assertRaisesRegex(ValueError, 'outside the dictionary'):
            TagClassifier().fit(create_examples(), ['study'])

        with self.assertRaisesRegex(ValueError, 'empty'):
            TagClassifier().fit(create_examples(), [])

    def test_deduplication_preserves_significant_symbols(self):
        cpp_text = 'C++ example of configuring a work application and server'
        csharp_text = 'C# example of configuring a work application and server'
        cpp_note = Note(Path('cpp.md'), cpp_text, {'cpp'}, cpp_text)
        csharp_note = Note(Path('csharp.md'), csharp_text, {'csharp'}, csharp_text)
        duplicate_body = cpp_text.upper().replace(' ', '  ')
        duplicate = Note(Path('copy.md'), duplicate_body, {'cpp'}, duplicate_body)

        self.assertEqual(training_notes([cpp_note, csharp_note, duplicate]), [cpp_note, csharp_note])

    def test_multilabel_predictions(self):
        notes = create_examples()
        for note in notes[:4]:
            note.tags.add('backend')

        classifier = TagClassifier().fit(notes, ['work_info', 'study', 'backend'])
        self.assertEqual(set(classifier.suggest('server deployment', threshold=0.5)), {'work_info', 'backend'})

    def test_calls_before_fit_and_invalid_thresholds(self):
        with self.assertRaisesRegex(ValueError, 'Train the classifier'):
            TagClassifier().scores('server')

        for threshold in (0, 1, -1, float('nan')):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                TagClassifier().suggest('server', threshold=threshold)

    def test_failed_retraining_preserves_model(self):
        classifier = TagClassifier().fit(create_examples(), ['work_info', 'study'])
        previous_scores = classifier.scores('server deployment')

        with self.assertRaises(ValueError):
            classifier.fit(create_examples()[:1], ['work_info'])

        self.assertEqual(classifier.scores('server deployment'), previous_scores)
