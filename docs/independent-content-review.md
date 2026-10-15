# Independent content review: Python functions and recursion draft

**Reviewer:** Codex (independent of the pack's named author, Claude L1)

**Date:** 2026-10-14 (America/Los_Angeles)

**Pack:** `python-functions-recursion`, `m1-draft.1`

**Decision:** Changes requested. The pack remains `draft`; all answer keys remain `candidate`.

## Scope and method

I read all 5 concepts, 5 lessons, 17 items (including their hints and candidate keys), 3 rubrics, and 8 source records. I checked the prerequisite order, item-family and held-out design, and official Python 3.12 documentation. The repository's content test executed the authored trace snippets and compared their results with the candidate keys. I separately assessed quoted and unquoted forms of both string-valued trace answers through the assessment engine. The review receipts in the pack approve 34 individual records and request changes to the 4 records below; an approval of a record does not promote the whole pack or any candidate key to release status.

## Changes required before full approval

| ID | Finding | Required correction |
| --- | --- | --- |
| `scope-keyword-transfer-01` | The value is a string. The worked hint displays `"Hi Ana?"`, but the candidate key accepts only `Hi Ana?`; the assessment engine marks the quoted Python string value incorrect. | State the expected answer format in the prompt or accept both unquoted and Python string-literal forms. Check the new accepted forms against the engine. |
| `recursive-case-transfer-01` | The worked hint displays `"cba"`, but the candidate key accepts only `cba`. A learner who supplies the quoted string value is marked incorrect. | Apply the same format or accepted-answer correction. |
| `recursion-recognize-choice-01` | The selected definition calls itself but has no stopping case. It is technically the only self-call among the choices, yet it models a broken recursive function immediately before the base-case lesson. | Replace it with a terminating recursive example, or explicitly ask which definition contains a self-call **even though it will not terminate**. Update the worked hint accordingly. |
| `lesson-recursion-as-self-call` | `steps(n)` reaches its base case for positive integers, but not for zero or negative inputs; no input domain is stated. A learner may infer that every input terminates. | State the positive-input domain or guard nonpositive inputs, and explain that making progress toward a reachable base case is required. |

For the two string items, the engine returned `correct` for the unquoted candidate and `incorrect` for its quoted Python representation. The exact-value behavior is consistent with the current implementation; the item wording and hints make the accepted-answer boundary ambiguous.

## Approved scope and limits

The remaining scored keys matched their snippets or listed choices. The other lessons, hints, and rubrics were consistent with the cited Python behavior at the level reviewed. The source records point to official Python 3.12 pages, including [function definitions and recursion](https://docs.python.org/3.12/tutorial/controlflow.html#defining-functions), [calls and return values](https://docs.python.org/3.12/reference/expressions.html#calls), [local name binding](https://docs.python.org/3.12/reference/executionmodel.html#naming-and-binding), [RecursionError](https://docs.python.org/3.12/library/exceptions.html#RecursionError), and [the recursion limit](https://docs.python.org/3.12/library/sys.html#sys.getrecursionlimit).

This review covers the current five-concept slice. The project brief calls for approximately 20 related concepts, so it does not certify the eventual full pack. It does not establish that the learning policy improves delayed retention or transfer. Before promotion, correct the four records, version changed content appropriately, rerun content and assessment checks, and conduct a new independent review of the changed records and any added concepts. The local preview must continue to label this pack as a development draft until that work is complete.
