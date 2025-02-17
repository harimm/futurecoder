import json
import os
import random
import re
from pathlib import Path

from littleutils import only

import core.utils
from core import translation as t
from core.checker import check_entry, runner
from core.text import step_test_entries, get_predictions, load_chapters
from core.utils import highlighted_markdown, make_test_input_callback

core.utils.TESTING = True

random.seed(0)


def test_steps():
    lang = os.environ.get("FUTURECODER_LANGUAGE", "en")
    t.set_language(lang)
    list(load_chapters())
    runner.reset()
    transcript = []
    for page, step, substep, entry in step_test_entries():
        program = substep.program
        is_message = substep != step

        output_parts = []
        def output_callback(data):
            output_parts.extend(data["parts"])

        step.pre_run(runner)

        response = check_entry(
            entry,
            input_callback=make_test_input_callback(step.stdin_input),
            output_callback=output_callback,
        )
        response["output_parts"] = output_parts
        normalise_response(response, is_message, substep)

        transcript_item = dict(
            program=program.splitlines(),
            page=page.title,
            step=step.__name__,
            response=response,
        )
        transcript.append(transcript_item)

        if step.get_solution and not is_message:
            get_solution = "".join(step.get_solution["tokens"])
            assert "def solution(" not in get_solution
            assert "returns_stdout" not in get_solution
            assert get_solution.strip() in program
            transcript_item["get_solution"] = get_solution.splitlines()
            if step.parsons_solution:
                is_function = transcript_item["get_solution"][0].startswith(
                    "def "
                )
                assert len(step.get_solution["lines"]) >= 4 + is_function

        assert response["passed"] == (not is_message)

    dirpath = Path(__file__).parent / "golden_files" / lang
    dirpath.mkdir(parents=True, exist_ok=True)
    path = dirpath / "test_transcript.json"
    if os.environ.get("FIX_TESTS", 0):
        dump = json.dumps(transcript, indent=4, sort_keys=True)
        path.write_text(dump)
    else:
        assert transcript == json.loads(path.read_text())


def normalise_output(s):
    s = re.sub(r" at 0x\w+>", " at 0xABC>", s)
    return s


def normalise_response(response, is_message, substep):
    response["result"] = response.pop("output_parts")
    for line in response["result"]:
        line["text"] = normalise_output(line["text"])
        if line["type"] == "traceback":
            line["text"] = line["text"].splitlines()

    response.pop("birdseye_objects", None)
    del response["error"]
    del response["output"]

    response["prediction"] = get_predictions(substep)
    if not response["prediction"]["choices"]:
        del response["prediction"]

    if is_message:
        response["message"] = only(response.pop("messages"))
        assert response["message"] == highlighted_markdown(substep.text)
    else:
        assert response.pop("messages") == []
        response["message"] = ""
