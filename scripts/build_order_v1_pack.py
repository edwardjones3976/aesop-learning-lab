"""Deterministic generator for the paired order-v1 micro-unit pack.

Builds content/drafts/order-v1-invented-pack.json from:
- content/drafts/invented-lexicon-v1.json
- content/drafts/invented-lexicon-authoring.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path


def generate_order_v1_pack_data(
    lexicon_path: Path | str,
    authoring_path: Path | str,
) -> dict:
    lexicon_file = Path(lexicon_path)
    authoring_file = Path(authoring_path)

    lexicon = json.loads(lexicon_file.read_text(encoding="utf-8"))
    authoring = json.loads(authoring_file.read_text(encoding="utf-8"))

    methods = [
        {
            "id": "worked_then_retrieve",
            "name": "Worked example then retrieval",
            "description": "Worked example and explanation, followed by retrieval and feedback.",
        },
        {
            "id": "predict_first",
            "name": "Prediction question first",
            "description": "Prediction attempt first, followed by worked example, explanation, and feedback.",
        },
    ]

    units = []
    for lex_unit in lexicon["units"]:
        word = lex_unit["word"]
        gloss = lex_unit["gloss"]
        check_src = lex_unit["check"]

        auth_entry = authoring[gloss]
        ex_sentences = auth_entry["example_sentences"]

        s0 = ex_sentences[0]
        s1 = ex_sentences[1]

        if "{w}" not in s0 or "{w}" not in s1:
            raise ValueError(f"Sentence for {word} ({gloss}) lacks {{w}}")

        # E: worked example and explanation
        # 'The invented word W means 'G'. Example: <example_sentences[0] with {w} replaced by W, keeping '(gloss)'>'
        s0_rendered = s0.replace("{w}", word)
        e_segment = f"The invented word {word} means '{gloss}'. Example: {s0_rendered}"

        # Q: the retrieval or prediction question
        # 'Question: in this sentence, what does W mean? <example_sentences[1] with {w} replaced by W and the ' (gloss)' parenthetical REMOVED>'
        s1_rendered = s1.replace("{w}", word)
        # Remove ' (gloss)' parenthetical
        s1_no_paren = re.sub(r" \([^)]*\)", "", s1_rendered)
        q_segment = f"Question: in this sentence, what does {word} mean? {s1_no_paren}"

        # F: corrective feedback
        # 'Answer: W means 'G'.'
        f_segment = f"Answer: {word} means '{gloss}'."

        variants = {
            "worked_then_retrieve": f"{e_segment}\n{q_segment}\n{f_segment}",
            "predict_first": f"{q_segment}\n{e_segment}\n{f_segment}",
        }

        # check prompt: 'What does <word> mean?'. Use lexicon's prompt if exactly that, else that text.
        standard_prompt = f"What does {word} mean?"
        prompt = check_src["prompt"] if check_src.get("prompt") == standard_prompt else standard_prompt

        check = {
            "id": f"{word}-day7",
            "family_id": f"{word}-meaning",
            "prompt": prompt,
            "answer_key": {
                "status": "candidate",
                "accepted": list(check_src["accepted"]),
            },
            "check_delay_days": 7,
            "held_out": True,
        }

        unit = {
            "id": word,
            "target": {
                "word": word,
                "gloss": gloss,
            },
            "variants": variants,
            "check": check,
            "practice": [],
        }
        units.append(unit)

    return {
        "kind": "micro_unit",
        "schema_version": "micro-unit-pack/1",
        "pack_id": "invented-vocabulary-order-v1",
        "methods": methods,
        "units": units,
    }


def serialize_pack(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def build_pack(
    lexicon_path: Path | str = Path("content/drafts/invented-lexicon-v1.json"),
    authoring_path: Path | str = Path("content/drafts/invented-lexicon-authoring.json"),
    output_path: Path | str = Path("content/drafts/order-v1-invented-pack.json"),
) -> None:
    data = generate_order_v1_pack_data(lexicon_path, authoring_path)
    content = serialize_pack(data)
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    # Write using binary mode with LF to guarantee byte determinism across platforms
    out_file.write_bytes(content.encode("utf-8"))


if __name__ == "__main__":
    build_pack()
    print("Successfully built content/drafts/order-v1-invented-pack.json")
