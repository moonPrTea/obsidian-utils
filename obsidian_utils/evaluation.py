from typing import Iterable

from sklearn.metrics import precision_recall_fscore_support
from sklearn.model_selection import train_test_split

from .classifier import TagClassifier, training_notes
from .constants import DEFAULT_THRESHOLD, MIN_EVALUATION_NOTES, RANDOM_STATE, TEST_SIZE
from .vault import Note


def split_examples(notes: Iterable[Note]) -> tuple[list[Note], list[Note]]:
    examples = training_notes(notes)
    if len(examples) < MIN_EVALUATION_NOTES:
        raise ValueError(f'Evaluation requires at least {MIN_EVALUATION_NOTES} distinct labelled notes')

    training_samples, testing_samples = train_test_split(
        examples,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
    )

    return training_samples, testing_samples


def evaluate(notes: Iterable[Note], tags: Iterable[str], threshold: float = DEFAULT_THRESHOLD) -> dict:
    if not 0 < threshold < 1:
        raise ValueError('Threshold must be greater than 0 and less than 1')

    category_tags = sorted(set(tags))
    if not category_tags:
        raise ValueError('The tag dictionary is empty')

    training_samples, testing_samples = split_examples(notes)
    for note in training_samples + testing_samples:
        if note.tags - set(category_tags):
            raise ValueError(f'{note.path.name}: tags outside the dictionary were found')

    missing_examples = [
        tag for tag in category_tags
        if not any(tag in note.tags for note in testing_samples)
        or not any(tag not in note.tags for note in testing_samples)
    ]
    if missing_examples:
        raise ValueError(
            'The test split needs examples with and without each tag: '
            + ', '.join(missing_examples) + '. Add more labelled notes.'
        )

    classifier = TagClassifier().fit(training_samples, category_tags)
    predictions = [set(classifier.suggest(note.text, threshold)) for note in testing_samples]
    tag_metrics = {}

    for tag in category_tags:
        actual_labels = [tag in note.tags for note in testing_samples]
        predicted_labels = [tag in predicted_tags for predicted_tags in predictions]
        precision, recall, f1, _ = precision_recall_fscore_support(
            actual_labels,
            predicted_labels,
            average='binary',
            zero_division=0,
        )
        positive_count = sum(actual_labels)
        tag_metrics[tag] = {
            'precision': float(precision),
            'recall': float(recall),
            'f1': float(f1),
            'support': positive_count,
            'negative_support': len(testing_samples) - positive_count,
        }

    results = [
        {
            'file': str(note.path),
            'actual_tags': sorted(note.tags),
            'predicted_tags': sorted(predicted_tags),
        }
        for note, predicted_tags in zip(testing_samples, predictions)
    ]
    exact_matches = sum(note.tags == predicted_tags for note, predicted_tags in zip(testing_samples, predictions))

    return {
        'train_size': len(training_samples),
        'test_size': len(testing_samples),
        'threshold': threshold,
        'per_tag': tag_metrics,
        'coverage': sum(bool(predicted_tags) for predicted_tags in predictions) / len(testing_samples),
        'exact_match': exact_matches / len(testing_samples),
        'results': results,
    }
