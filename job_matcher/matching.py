def extract_skills(text: str, skill_map: dict) -> set[str]:
    text = text.lower()
    found = set()
    for canonical, aliases in skill_map.items():
        if any(a in text for a in aliases):
            found.add(canonical)
    return found