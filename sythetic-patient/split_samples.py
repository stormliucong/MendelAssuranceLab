import json
from pathlib import Path

src = Path(__file__).parent / "filtered_llm_samples.json"
out_dir = src.parent / "patients"
out_dir.mkdir(exist_ok=True)

with src.open() as f:
    samples = json.load(f)

for sample in samples:
    (out_dir / f"{sample['id']}.json").write_text(
        json.dumps(sample, indent=2, ensure_ascii=False)
    )

print(f"Wrote {len(samples)} files to {out_dir}")
