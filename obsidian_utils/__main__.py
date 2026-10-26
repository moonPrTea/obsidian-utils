import argparse
import json
import sys
from pathlib import Path

from .constants import DEFAULT_CONFIG_FILE, DEFAULT_THRESHOLD
from .vault import Note, load_vault


def inspect_vault(vault_root: Path, categories: dict, notes: list[Note], skipped_paths: list) -> dict:
    return {
        'categories': {
            tag: {
                'file': category['path'].relative_to(vault_root).as_posix(),
                'description': category['description'],
                'examples': sum(tag in note.tags for note in notes),
            }
            for tag, category in categories.items()
        },
        'usable_notes': len(notes),
        'unlabelled': sum(not note.tags for note in notes),
        'skipped_short': skipped_paths,
    }


def suggest_tags(vault_root: Path, categories: dict, notes: list[Note], threshold: float) -> dict:
    from .classifier import TagClassifier, training_notes

    training_samples = training_notes(notes)
    pending_notes = [note for note in notes if not note.tags]
    suggestions = []

    if pending_notes:
        classifier = TagClassifier().fit(training_samples, categories)
        for note in pending_notes:
            tag_scores = dict(sorted(classifier.scores(note.text).items(), key=lambda item: item[1], reverse=True))
            proposed_tags = [tag for tag, score in tag_scores.items() if score >= threshold]
            suggestions.append({
                'file': note.path.relative_to(vault_root).as_posix(),
                'tags': proposed_tags,
                'scores': tag_scores,
                'needs_review': True,
                'abstained': not proposed_tags,
            })

    return {'training_notes': len(training_samples), 'threshold': threshold, 'suggestions': suggestions}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Suggest existing Obsidian tags without changing notes')
    parser.add_argument('command', choices=['inspect', 'suggest', 'evaluate'])
    parser.add_argument('vault', help='Path to the Obsidian vault')
    parser.add_argument('--config', default=DEFAULT_CONFIG_FILE, help='Category index path relative to the vault')
    parser.add_argument('--exclude', action='append', default=[], help='Exclude a relative path pattern; repeatable')
    parser.add_argument('--threshold', type=float, default=DEFAULT_THRESHOLD, help='Minimum score for a tag suggestion')
    arguments = parser.parse_args(argv)
    if not 0 < arguments.threshold < 1:
        parser.error('--threshold must be greater than 0 and less than 1')

    try:
        vault_root, categories, notes, skipped_paths = load_vault(
            arguments.vault, arguments.config, arguments.exclude,
        )
        if arguments.command == 'inspect':
            result = inspect_vault(vault_root, categories, notes, skipped_paths)
        elif arguments.command == 'suggest':
            result = suggest_tags(vault_root, categories, notes, arguments.threshold)
            result['skipped_short'] = skipped_paths
        else:
            from .evaluation import evaluate

            result = evaluate(notes, categories, arguments.threshold)
            for prediction in result['results']:
                prediction['file'] = Path(prediction['file']).relative_to(vault_root).as_posix()
            result['skipped_short'] = skipped_paths

        print(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
