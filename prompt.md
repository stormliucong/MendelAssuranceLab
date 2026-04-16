For each patient in the sythetic folder. read its profile. Find relevant policies in the policy document, and then answer each question in the `question.md`

For each patient output an `answer_<patient_id>.json` by following the example in `answer_template.json` and put them into the QA results.


# Answer schema (JK)
The answer json schema is defined as following
`policy_document_name` - name of the document
`q1` - choose on of this "yes | no | unknow" 
`q2` - xxxx

## You can't do
- read or modify ground-truth/
- read or modify eval-results/
- read or modify README.md









