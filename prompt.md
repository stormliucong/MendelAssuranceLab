For each patient in the `sythetic-patient/patients` folder, read its `patient_info` field, and find top 1 relevant insurance policy in the `policy-documents/policy_11` folder for the given patient, use the calculate the `md5` for the identified relevant policies using `md5sum file_name.pdf`, and then answer each question in the `question.json` based on the description in that policy and patient medical conditions described in the `patient_info` field. For each question, it will be a single choice question and you should select one from the `options` field. put calculated `md5` for the identified policy document into `identified_md5` field. For each patient output an `answer_<id>.json` by following the example in `answer_example.json` and put it into the `QA-results`. 


## You CAN NOT do
- read or modify `ground-truth/`
- read or modify `eval-results/`
- read or modify `README.md`
- read or modify `question.json`








