from __future__ import annotations

import csv
import io
import json
import xml.etree.ElementTree as ET

from .contracts import Experiment


def experiment_csv(experiment: Experiment) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["seed", "candidate_run", "candidate_verdict", "baseline_run", "baseline_verdict",
                     "collision_delta", "force_delta_n", "duration_delta_s", "failure_reasons"])
    for pair in experiment.pairs:
        writer.writerow([pair.seed, pair.candidate_run.id, pair.candidate_run.verdict, pair.baseline_run.id,
                         pair.baseline_run.verdict, pair.metric_deltas.get("collisions"),
                         pair.metric_deltas.get("max_contact_force_n"), pair.metric_deltas.get("sim_duration_s"),
                         ";".join(pair.failure_reasons)])
    return output.getvalue()


def experiment_junit(experiment: Experiment) -> str:
    failures = sum(bool(pair.failure_reasons) for pair in experiment.pairs) + (1 if experiment.verdict == "fail" else 0)
    suite = ET.Element("testsuite", name=f"Praxis experiment {experiment.id}",
                       tests=str(len(experiment.pairs) + 1), failures=str(failures))
    for pair in experiment.pairs:
        case = ET.SubElement(suite, "testcase", classname="praxis.seed", name=f"seed_{pair.seed}")
        if pair.failure_reasons:
            failure = ET.SubElement(case, "failure", message=", ".join(pair.failure_reasons))
            failure.text = json.dumps(pair.metric_deltas)
        ET.SubElement(case, "system-out").text = f"candidate={pair.candidate_run.id} baseline={pair.baseline_run.id}"
    gate_case = ET.SubElement(suite, "testcase", classname="praxis.gates", name="experiment_gate")
    if experiment.verdict == "fail":
        failed_gates = [result["id"] for result in experiment.gate_results if not result["passed"]]
        ET.SubElement(gate_case, "failure", message=", ".join(failed_gates)).text = json.dumps(experiment.summary)
    return ET.tostring(suite, encoding="unicode", xml_declaration=True)

