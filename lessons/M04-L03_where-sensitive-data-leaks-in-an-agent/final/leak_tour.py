"""
M04-L03: where sensitive data leaks in an agent. A naive prior-auth reviewer, run offline, writes the six
artifacts real agents produce; then a canary scan counts the identifiers in each one.

    uv run python lessons/M04-L03_where-sensitive-data-leaks-in-an-agent/final/leak_tour.py

Leak points: 1 the prompt  2 tool results (the model's context)  3 the transcript  4 debug logs
             5 traces      6 error messages   (+ the final answer, which repeats what the model saw)
"""
from __future__ import annotations

import asyncio
import json
import traceback
from pathlib import Path

from course_data import patients
from sentinel.privacy import canaries_from, scan_text
from sentinel.privacy.pa_tools import PA_DECISIONS, build_pa_tools

OUT = Path(__file__).resolve().parent / "workspace"

PROMPT = ("Please review PA-2001 for Maria Delgado, DOB 03/14/1961, MRN 4829173. "
          "Her SSN is 912-45-6789 if you need to look her up.")                  # users paste identifiers


async def naive_run() -> dict[str, str]:
    OUT.mkdir(exist_ok=True)
    get_case, _, _ = build_pa_tools(minimized=False)
    artifacts = {"1. prompt": PROMPT}
    result = await get_case.handler({"request_id": "PA-2001"})
    tool_text = result["content"][0]["text"]
    artifacts["2. tool result (model context)"] = tool_text                      # the whole record
    artifacts["3. transcript"] = json.dumps([{"role": "user", "content": PROMPT},
                                             {"role": "tool", "content": tool_text}])
    artifacts["4. debug log"] = f"DEBUG get_prior_auth_case args={{'request_id': 'PA-2001'}} -> {tool_text}"
    artifacts["5. trace span"] = json.dumps({"name": "tool.get_prior_auth_case",
                                             "attributes": {"tool.input": "PA-2001", "tool.output": tool_text}})
    try:                                                                          # a validation error...
        case = json.loads(tool_text)
        raise ValueError(f"criterion lookup failed for case {case}")              # ...that prints the record
    except ValueError:
        artifacts["6. error message"] = traceback.format_exc()
    rec, crit, why = PA_DECISIONS["PA-2001"]
    artifacts["+ final answer"] = f"Maria Delgado (MRN 4829173): {rec}, criterion {crit}: {why}."
    for name, text in artifacts.items():
        (OUT / (name.split(" ", 1)[1].split(" (")[0].replace(" ", "_") + ".txt")).write_text(text, encoding="utf-8")
    return artifacts


def main() -> None:
    canaries = canaries_from(patients())
    artifacts = asyncio.run(naive_run())
    print(f"{'Leak point':<34} {'Identifiers':>11}  Examples")
    for name, text in artifacts.items():
        hits = scan_text(text, canaries)
        print(f"{name:<34} {len(hits):>11}  {', '.join(h.split('.', 1)[1] for h in hits[:5])}")
    print(f"\nArtifacts written to {OUT}")


if __name__ == "__main__":
    main()
