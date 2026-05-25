# Sample Documents

These three documents are the corpus the evaluation harness uses. They
were authored from scratch for this project — they're not real company
policies and contain no PII or copyrighted content.

| File | Topic |
|------|-------|
| `employee_handbook.md`   | PTO, sick leave, parental leave, remote work |
| `it_security_policy.md`  | Passwords, MFA, VPN, data classification, incident reporting |
| `helpdesk_sop.md`        | Ticket severities, lifecycle, escalation rules |

## How they're used

`evals/datasets/golden_qa.jsonl` contains 20 questions written against
these documents. Half are factual lookups (the answer should be cited
to a specific source); half are out-of-scope questions where the
correct behavior is to abstain.

To run the eval against a fresh corpus:

```bash
make eval-seed   # uploads these three docs via the API
make eval        # runs the golden Q&A and writes a report
```

The report lands in `evals/reports/`.
