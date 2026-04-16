# This is for Human Only

## To Do List

### Prepare the benchmark and prompts
- Populate `sythetic-patient/`, split them by patient, one file one patient, with `patient_id`
- Populate `policy-document/`, add file name and make it clearly.
- Populate `ground-truth/`, one file per patient, with `patient_id`
- Populate `question.json`, provide questions
- Add more description and explanation in `prompt.md`
- write `eval.py` to do the evaluation and generate the eval.csv
- write a `answer_example.json`, provide examples for agent
- create gitignore to omit policy-document.

### Test the agent
- Use claude code to run the test. Start prompt will be "Look at `prompt.md` and do the work"

