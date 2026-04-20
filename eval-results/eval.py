# Input: ground-truth/final_ground_truth.json and QA-results/
# Output: evaluation results in eval-results/
# for QA-results, each file is <patient_id>.json, with the following format similar to the answer_example.json

# Output results including per patient including the following fields:
# - patient_id
# - policy_match: whether the predicted policy matches the ground truth policy (by md5)
# - q0_accuracy: whether the predicted answer for q0 matches the ground truth answer for q0
# - q1_accuracy: whether the predicted answer for q1 matches the ground truth answer for q1
# - q2_accuracy: whether the predicted answer for q2 matches the ground truth answer for q2
# - q3_accuracy: whether the predicted answer for q3 matches the ground truth answer for q3
# - q4_accuracy: whether the predicted answer for q4 matches the ground truth answer for q4
# - q5_accuracy: whether the predicted answer for q5 matches the ground truth answer for q5
# - q6_accuracy: whether the predicted answer for q6 matches the ground truth answer for q6
# - q7_accuracy: whether the predicted answer for q7 matches the ground truth answer for q7
# - q8_accuracy: whether the predicted answer for q8 matches the ground truth answer for q8

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GT_PATH = ROOT / "ground-truth" / "final_ground_truth.json"
QA_DIR = ROOT / "QA-results"
OUT_DIR = ROOT / "eval-results"

QUESTIONS = [f"Q{i}" for i in range(9)]


def load_prediction(patient_id: str):
    # Files are written as `answer_<patient_id>.json` per prompt.md.
    candidates = [
        QA_DIR / f"answer_{patient_id}.json",
        QA_DIR / f"{patient_id}.json",
    ]
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        return None
    with path.open() as f:
        data = json.load(f)
    # File may be {patient_id: {...}} or just the answer dict directly.
    if isinstance(data, dict) and patient_id in data and isinstance(data[patient_id], dict):
        return data[patient_id]
    if isinstance(data, dict) and len(data) == 1:
        only = next(iter(data.values()))
        if isinstance(only, dict):
            return only
    return data


def evaluate_patient(patient_id: str, gt: dict, pred: dict) -> dict:
    row = {"patient_id": patient_id}
    row["policy_match"] = pred.get("identified_md5") == gt.get("expected_md5")
    for q in QUESTIONS:
        row[f"{q.lower()}_accuracy"] = pred.get(q) == gt.get(q)
    return row


def main() -> None:
    with GT_PATH.open() as f:
        ground_truth = json.load(f)

    results = []
    for patient_id, gt in ground_truth.items():
        pred = load_prediction(patient_id)
        if pred is None:
            continue
        results.append(evaluate_patient(patient_id, gt, pred))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "eval_results.json"
    csv_path = OUT_DIR / "eval_results.csv"
    summary_path = OUT_DIR / "eval_summary.json"

    with json_path.open("w") as f:
        json.dump(results, f, indent=2)

    fieldnames = [
        "patient_id",
        "policy_match",
        *(f"{q.lower()}_accuracy" for q in QUESTIONS),
    ]
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    n = len(results)
    summary = {
        "total_ground_truth": len(ground_truth),
        "scored_patients": n,
    }
    if n:
        summary["policy_match_rate"] = sum(r["policy_match"] for r in results) / n
        for q in QUESTIONS:
            key = f"{q.lower()}_accuracy"
            summary[f"{key}_rate"] = sum(r[key] for r in results) / n

    with summary_path.open("w") as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {summary_path}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
