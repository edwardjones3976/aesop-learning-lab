"""Deterministic generator for the invented lexicon micro-units.

Generates 100 phonotactically valid, unique invented words with everyday English glosses
and four distinct lesson method variants (retrieval, keyword, example_sentence, rule_drill),
plus held-out delayed evaluation checks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
from typing import Any, Dict, List, Tuple

# Default seed for deterministic generation
DEFAULT_SEED = 20261021

METHOD_DEFINITIONS = [
    {
        "id": "retrieval",
        "name": "Cued Retrieval Practice",
        "description": "Show the pair, then prompt the learner to recall the gloss before revealing it.",
    },
    {
        "id": "keyword",
        "name": "Keyword Mnemonic",
        "description": "A keyword mnemonic linking the sound to an English keyword, then to the meaning, with a vivid image sentence.",
    },
    {
        "id": "example_sentence",
        "name": "Contextual Examples",
        "description": "The word used in two short English-frame sentences that make the meaning clear.",
    },
    {
        "id": "rule_drill",
        "name": "Rule Then Drill",
        "description": "A short explicit definition statement followed by three quick drill lines.",
    },
]

# 50 concrete, everyday nouns and their acceptable answer variants
NOUN_GLOSSES: List[Tuple[str, List[str]]] = [
    ("kettle", ["kettle", "tea kettle"]),
    ("bucket", ["bucket", "pail"]),
    ("pillow", ["pillow", "cushion"]),
    ("blanket", ["blanket", "quilt"]),
    ("candle", ["candle", "taper"]),
    ("mirror", ["mirror", "looking glass"]),
    ("ladder", ["ladder", "stepladder"]),
    ("hammer", ["hammer", "mallet"]),
    ("shovel", ["shovel", "spade"]),
    ("needle", ["needle", "sewing needle"]),
    ("anchor", ["anchor"]),
    ("barrel", ["barrel", "cask"]),
    ("basket", ["basket", "hamper"]),
    ("bottle", ["bottle", "flask"]),
    ("bridge", ["bridge", "overpass"]),
    ("button", ["button"]),
    ("carpet", ["carpet", "rug"]),
    ("castle", ["castle", "fortress"]),
    ("chimney", ["chimney", "smokestack"]),
    ("compass", ["compass"]),
    ("cradle", ["cradle", "crib"]),
    ("curtain", ["curtain", "drape"]),
    ("dagger", ["dagger", "dirk"]),
    ("drawer", ["drawer"]),
    ("feather", ["feather", "plume"]),
    ("fence", ["fence", "paling"]),
    ("fountain", ["fountain"]),
    ("furnace", ["furnace", "boiler"]),
    ("garlic", ["garlic"]),
    ("helmet", ["helmet"]),
    ("jacket", ["jacket", "coat"]),
    ("lantern", ["lantern", "lamp"]),
    ("locket", ["locket", "pendant"]),
    ("mattress", ["mattress", "bedding"]),
    ("meadow", ["meadow", "pasture"]),
    ("mortar", ["mortar"]),
    ("necklace", ["necklace", "choker"]),
    ("orchard", ["orchard", "grove"]),
    ("pebble", ["pebble", "stone"]),
    ("quiver", ["quiver", "arrow case"]),
    ("ribbon", ["ribbon", "band"]),
    ("saddle", ["saddle"]),
    ("scissors", ["scissors", "shears"]),
    ("sponge", ["sponge"]),
    ("tunnel", ["tunnel", "underpass"]),
    ("valley", ["valley", "vale"]),
    ("wagon", ["wagon", "cart"]),
    ("whistle", ["whistle"]),
    ("window", ["window", "casement"]),
    ("anvil", ["anvil"]),
]

# 50 concrete, everyday verbs and their acceptable answer variants
VERB_GLOSSES: List[Tuple[str, List[str]]] = [
    ("to borrow", ["to borrow", "borrow"]),
    ("to whisper", ["to whisper", "whisper"]),
    ("to harvest", ["to harvest", "harvest"]),
    ("to sharpen", ["to sharpen", "sharpen"]),
    ("to polish", ["to polish", "polish"]),
    ("to scatter", ["to scatter", "scatter"]),
    ("to crumble", ["to crumble", "crumble"]),
    ("to stumble", ["to stumble", "stumble"]),
    ("to wander", ["to wander", "wander"]),
    ("to tremble", ["to tremble", "tremble"]),
    ("to kindle", ["to kindle", "kindle"]),
    ("to untie", ["to untie", "untie"]),
    ("to squeeze", ["to squeeze", "squeeze"]),
    ("to bounce", ["to bounce", "bounce"]),
    ("to splash", ["to splash", "splash"]),
    ("to gallop", ["to gallop", "gallop"]),
    ("to paddle", ["to paddle", "paddle"]),
    ("to juggle", ["to juggle", "juggle"]),
    ("to buckle", ["to buckle", "buckle"]),
    ("to tickle", ["to tickle", "tickle"]),
    ("to sprout", ["to sprout", "sprout"]),
    ("to wither", ["to wither", "wither"]),
    ("to shimmer", ["to shimmer", "shimmer"]),
    ("to swallow", ["to swallow", "swallow"]),
    ("to strangle", ["to strangle", "strangle"]),
    ("to wrestle", ["to wrestle", "wrestle"]),
    ("to slumber", ["to slumber", "slumber"]),
    ("to ponder", ["to ponder", "ponder"]),
    ("to shatter", ["to shatter", "shatter"]),
    ("to glisten", ["to glisten", "glisten"]),
    ("to plunge", ["to plunge", "plunge"]),
    ("to scramble", ["to scramble", "scramble"]),
    ("to trample", ["to trample", "trample"]),
    ("to trickle", ["to trickle", "trickle"]),
    ("to clamber", ["to clamber", "clamber"]),
    ("to linger", ["to linger", "linger"]),
    ("to dwindle", ["to dwindle", "dwindle"]),
    ("to beckon", ["to beckon", "beckon"]),
    ("to bestow", ["to bestow", "bestow"]),
    ("to engulf", ["to engulf", "engulf"]),
    ("to fathom", ["to fathom", "fathom"]),
    ("to garner", ["to garner", "garner"]),
    ("to ignite", ["to ignite", "ignite"]),
    ("to muster", ["to muster", "muster"]),
    ("to pilfer", ["to pilfer", "pilfer"]),
    ("to ravage", ["to ravage", "ravage"]),
    ("to saunter", ["to saunter", "saunter"]),
    ("to throttle", ["to throttle", "throttle"]),
    ("to unravel", ["to unravel", "unravel"]),
    ("to vanish", ["to vanish", "vanish"]),
]


def load_excluded_words() -> set[str]:
    """Load the committed exclusion list of words the generator must skip."""
    excluded_path = Path(__file__).resolve().parent / "excluded_words.txt"
    if not excluded_path.exists():
        raise FileNotFoundError(f"Excluded words file not found at {excluded_path}")
    with open(excluded_path, "r", encoding="utf-8") as f:
        return set(
            line.strip().lower()
            for line in f
            if line.strip() and not line.strip().startswith("#")
        )


def load_authoring_data() -> Dict[str, Dict[str, Any]]:
    """Load the unit-specific authored texts for all 100 glosses."""
    authoring_path = (
        Path(__file__).resolve().parent.parent
        / "content"
        / "drafts"
        / "invented-lexicon-authoring.json"
    )
    if not authoring_path.exists():
        raise FileNotFoundError(f"Authoring data file not found at {authoring_path}")
    with open(authoring_path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_phonotactic_words(
    rng: random.Random, excluded_words: set[str], count: int = 100
) -> List[str]:
    """Deterministically generate pronounceable CV/CVC syllables, 2-3 syllables each, not in excluded_words."""
    onset_c = ["b", "d", "f", "g", "h", "j", "k", "l", "m", "n", "p", "r", "s", "t", "v", "w", "z"]
    vowels = ["a", "e", "i", "o", "u"]
    coda_c = ["l", "m", "n", "r", "s", "t", "k"]

    words: List[str] = []
    while len(words) < count:
        syll_count = rng.choice([2, 3])
        syllables: List[str] = []
        for _ in range(syll_count):
            s = rng.choice(onset_c) + rng.choice(vowels)
            if rng.random() < 0.3:
                s += rng.choice(coda_c)
            syllables.append(s)
        candidate = "".join(syllables)
        if len(candidate) >= 4 and candidate not in excluded_words and candidate not in words:
            words.append(candidate)
    return words


def build_lexicon_data(seed: int = DEFAULT_SEED) -> Dict[str, Any]:
    """Deterministically build the complete invented lexicon data structure."""
    rng = random.Random(seed)
    excluded_words = load_excluded_words()
    authoring_data = load_authoring_data()

    words = generate_phonotactic_words(rng, excluded_words, count=100)

    # Combine nouns and verbs, then randomly shuffle with same seed to ensure irregularity
    items = list(NOUN_GLOSSES + VERB_GLOSSES)
    rng.shuffle(items)

    units: List[Dict[str, Any]] = []

    for i in range(100):
        word = words[i]
        gloss, accepted = items[i]
        is_verb = gloss.startswith("to ")
        base = gloss[3:] if is_verb else gloss
        gloss_phrase = f"'to {base}'" if is_verb else f"'{gloss}'"

        auth = authoring_data[gloss]

        # 1. Retrieval variant (real retrieval: show word, prompt recall, answer on separate final line)
        retrieval = (
            f"Consider the invented word {word}.\n"
            f"What does {word} mean? Take a moment to recall or guess before checking below.\n"
            f"Answer: {word} means {gloss_phrase}, so remember that {gloss} is the meaning."
        )

        # 2. Keyword variant (sound-alike keyword + vivid image sentence connecting keyword to meaning)
        kw = auth["keyword"]
        # The word follows the meaning in brackets, as in the other methods, so the sentence reads naturally.
        mnem_sentence = auth["mnemonic_sentence"].format(w=f"({word})")
        keyword = (
            f"Think of {word} as {kw}. {mnem_sentence} "
            f"For instance, remember that {word} means {gloss_phrase} whenever you hear {kw}."
        )

        # 3. Example sentence variant (two unit-specific sentences implying meaning clearly)
        ex1 = auth["example_sentences"][0].format(w=word)
        ex2 = auth["example_sentences"][1].format(w=word)
        example_sentence = f"{ex1} {ex2}"

        # 4. Rule drill variant (explicit definition statement + 3 sensible unit-specific drills)
        drill1 = auth["rule_drills"][0].format(w=word)
        drill2 = auth["rule_drills"][1].format(w=word)
        drill3 = auth["rule_drills"][2].format(w=word)
        rule_drill = (
            f"Rule: {word} means {gloss_phrase}.\n"
            f"Drill 1: {drill1}\n"
            f"Drill 2: {drill2}\n"
            f"Drill 3: {drill3}"
        )

        # Delayed check
        wrong_example = items[(i + 1) % 100][0]

        unit = {
            "id": word,
            "word": word,
            "gloss": gloss,
            "variants": {
                "retrieval": retrieval,
                "keyword": keyword,
                "example_sentence": example_sentence,
                "rule_drill": rule_drill,
            },
            "check": {
                "prompt": f"What does {word} mean?",
                "accepted": accepted,
                "family_id": f"{word}-meaning",
                "check_delay_days": 7,
                "held_out": True,
                "wrong_example": wrong_example,
            },
        }
        units.append(unit)

    return {
        "seed": seed,
        "methods": METHOD_DEFINITIONS,
        "units": units,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate invented lexicon draft.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed for generation")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("content/drafts/invented-lexicon-v1.json"),
        help="Output JSON file path",
    )
    args = parser.parse_args()

    data = build_lexicon_data(seed=args.seed)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Generated {len(data['units'])} units to {args.output} (seed={args.seed})")


if __name__ == "__main__":
    main()
