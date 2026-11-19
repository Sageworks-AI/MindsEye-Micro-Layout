"""STUB. Wording only. The real language lives in PEACEBINFLOW/mindscript-core. Do not add grammar here."""
import statistics

PHRASES = {
    "section_shape": "This part looks like {shape_label}. Text is {font_pt} pt, lines {line} apart, margins {margin_pct}% of the page width.",
    "section_candidate": "This part matches no known shape yet. It is {drift} away from the closest one ({shape_label}). Saved as a candidate.",
    "texture": "The texture is {density}, with an {rhythm} rhythm.",
    "name_seen": "{name} appears in {n} places.",
    "restructure": "You keep coming back to {pattern}. The options are now 3 groups: {groups}.",
    "seed_word": "The owner pointed to the word {word}.",
    "window_compared": "You are comparing {a} with {b}.",
}

def say(kind, **vals):
    t = PHRASES.get(kind)
    if not t:
        return ""
    try:
        return t.format(**vals)
    except (KeyError, IndexError):
        return ""

def label(shape_id):
    return shape_id.replace("-", " ")

def density_word(avg_words):
    if avg_words < 15:
        return "airy"
    if avg_words <= 40:
        return "steady"
    return "dense"

def rhythm_word(para_words):
    if len(para_words) < 2:
        return "even"
    mean = sum(para_words) / len(para_words)
    if mean == 0:
        return "even"
    return "even" if statistics.pstdev(para_words) / mean < 0.35 else "uneven"
