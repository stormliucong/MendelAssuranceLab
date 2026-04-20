# This is for Human Only
- This repo is prepared for claude code agent to do the work
- Compare the results with RAG-based system

### Prepare the benchmark and prompts
- Populate `policy-document/`, add file name and make it clearly.
    - This folder is empty, you should add the subfolder (e.g. `policy_11`) and add policies to allow agent search for relevant documents for Q&A.
    - Modify `prompt.md` to replace `policy-documents/policy_11` with extra folder name (e.g. `policy-documents/policy_789`) where you want agent to search relevant files.

- Use `split_samples.py` to split file into per patient.

### Test the agent
- Clear the claude code session and memory before start the agent. 
- Use claude code to run the test. Start prompt will be "Look at `prompt.md` and do the work"
- After agent finished, run `eval.py` to generate evaluation results by comparing with ground-truth.

### To Do List
- check `ground-truth.json` by comparing with policy_11 based per patient results with explanation from claude code. only focus on those unmatched questions.
- run agent with `policy_789` and report eval results
- repeat agent run (same setting) several times and report variance.
