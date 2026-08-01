from __future__ import annotations

from story_generation.models.bible import StoryBible

from .issues import ValidationIssue, issue, validate_provenance


def _duplicates(values: list[str]) -> set[str]:
    return {value for value in values if values.count(value) > 1}


def validate_story_bible(bible: StoryBible) -> list[ValidationIssue]:
    issues = validate_provenance(bible)
    for character_id in sorted(_duplicates([item.character_id for item in bible.characters])):
        issues.append(issue("DUPLICATE_CHARACTER_ID", "characters", f"Duplicate character id: {character_id}"))
    for location_id in sorted(_duplicates([item.location_id for item in bible.world.locations])):
        issues.append(issue("DUPLICATE_LOCATION_ID", "world.locations", f"Duplicate location id: {location_id}"))
    prop_ids = [item.prop_id for item in bible.world.props]
    for prop_id in sorted(_duplicates(prop_ids)):
        issues.append(issue("DUPLICATE_PROP_ID", "world.props", f"Duplicate prop id: {prop_id}"))
    character_ids = {item.character_id for item in bible.characters}
    for index, prop in enumerate(bible.world.props):
        if prop.owner_character_id and prop.owner_character_id not in character_ids:
            issues.append(issue(
                "UNKNOWN_CHARACTER_REF", f"world.props[{index}].owner_character_id",
                f"Unknown character id: {prop.owner_character_id}",
            ))
    return issues
