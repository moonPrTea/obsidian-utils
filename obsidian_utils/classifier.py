from typing import Iterable

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from .constants import (
    DEFAULT_THRESHOLD, MAX_FEATURES, MAX_ITERATIONS,
    MIN_LABEL_EXAMPLES, NGRAM_RANGE, RANDOM_STATE,
)
from .vault import Note


def training_notes(notes: Iterable[Note]) -> list[Note]:
    unique_notes = {}

    for note in notes:
        if not note.tags or not note.text.strip():
            continue

        content_key = ' '.join(note.body.casefold().split())
        if content_key in unique_notes and unique_notes[content_key].tags != note.tags:
            raise ValueError(
                f'Conflicting tags for identical text: {unique_notes[content_key].path.name}, {note.path.name}'
            )

        unique_notes.setdefault(content_key, note)

    return list(unique_notes.values())


class TagClassifier:
    def __init__(self):
        self.tags = []
        self.classifiers = {}
        self.vectorizer = None

    def fit(self, notes: Iterable[Note], tags: Iterable[str]):
        category_tags = sorted(set(tags))
        if not category_tags:
            raise ValueError('The tag dictionary is empty')

        examples = training_notes(notes)
        for note in examples:
            if note.tags - set(category_tags):
                raise ValueError(f'{note.path.name}: tags outside the dictionary were found')

        insufficient_tags = []
        for tag in category_tags:
            positive_count = sum(tag in note.tags for note in examples)
            negative_count = len(examples) - positive_count
            if min(positive_count, negative_count) < MIN_LABEL_EXAMPLES:
                insufficient_tags.append(tag)

        if insufficient_tags:
            raise ValueError(
                f'At least {MIN_LABEL_EXAMPLES} positive and negative examples '
                'are required for each tag: ' + ', '.join(insufficient_tags)
            )

        vectorizer = TfidfVectorizer(
            ngram_range=NGRAM_RANGE,
            sublinear_tf=True,
            max_features=MAX_FEATURES,
        )
        feature_matrix = vectorizer.fit_transform([note.text for note in examples])
        classifiers = {}

        for tag in category_tags:
            classifier = LogisticRegression(
                max_iter=MAX_ITERATIONS,
                class_weight='balanced',
                random_state=RANDOM_STATE,
            )
            classifier.fit(feature_matrix, [int(tag in note.tags) for note in examples])
            classifiers[tag] = classifier

        self.tags = category_tags
        self.vectorizer = vectorizer
        self.classifiers = classifiers

        return self

    def scores(self, text: str) -> dict[str, float]:
        if self.vectorizer is None:
            raise ValueError('Train the classifier with fit first')

        feature_matrix = self.vectorizer.transform([text])
        if feature_matrix.nnz == 0:
            return {tag: 0.0 for tag in self.tags}

        return {
            tag: float(classifier.predict_proba(feature_matrix)[0, 1])
            for tag, classifier in self.classifiers.items()
        }

    def suggest(self, text: str, threshold: float = DEFAULT_THRESHOLD) -> list[str]:
        if not 0 < threshold < 1:
            raise ValueError('Threshold must be greater than 0 and less than 1')

        ranked_scores = sorted(self.scores(text).items(), key=lambda item: item[1], reverse=True)

        return [tag for tag, score in ranked_scores if score >= threshold]
