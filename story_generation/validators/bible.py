from __future__ import annotations

from story_generation.models.bible import StoryBible

from .issues import GenerationIssue, GenerationIssueCode, issue, stable_sort_issues, validate_constraints, validate_provenance


def _duplicates(values: list[str]) -> set[str]:
    return {value for value in values if values.count(value) > 1}


def validate_story_bible(bible: StoryBible) -> list[GenerationIssue]:
    issues = validate_provenance(bible)
    for character_id in sorted(_duplicates([item.character_id for item in bible.characters])):
        issues.append(issue(GenerationIssueCode.DUPLICATE_CHARACTER_ID, "characters", f"Duplicate character id: {character_id}"))
    for location_id in sorted(_duplicates([item.location_id for item in bible.world.locations])):
        issues.append(issue(GenerationIssueCode.DUPLICATE_LOCATION_ID, "world.locations", f"Duplicate location id: {location_id}"))
    prop_ids = [item.prop_id for item in bible.world.props]
    for prop_id in sorted(_duplicates(prop_ids)):
        issues.append(issue(GenerationIssueCode.DUPLICATE_PROP_ID, "world.props", f"Duplicate prop id: {prop_id}"))
    character_ids = {item.character_id for item in bible.characters}
    for index, prop in enumerate(bible.world.props):
        if prop.initial_owner_id and prop.initial_owner_id not in character_ids:
            issues.append(issue(
                GenerationIssueCode.UNKNOWN_CHARACTER_REF, f"world.props[{index}].initial_owner_id",
                f"Unknown character id: {prop.initial_owner_id}", [prop.initial_owner_id],
            ))
        if prop.initial_location_id and prop.initial_location_id not in {item.location_id for item in bible.world.locations}:
            issues.append(issue(GenerationIssueCode.UNKNOWN_LOCATION_REF, f"world.props[{index}].initial_location_id", "Unknown location.", [prop.initial_location_id]))
    for character in bible.characters:
        for relation_id in character.relationships:
            if relation_id not in character_ids:
                issues.append(issue(GenerationIssueCode.UNKNOWN_CHARACTER_REF, f"characters[{character.character_id}].relationships", "Unknown character.", [relation_id]))
        issues.extend(validate_constraints(character.constraints, f"characters[{character.character_id}].constraints"))
    issues.extend(validate_constraints(bible.world.constraints, "world.constraints"))
    issues.extend(validate_constraints(bible.global_constraints, "global_constraints"))
    return stable_sort_issues(issues)
