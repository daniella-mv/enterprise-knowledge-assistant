# Eval report — topk1 (20260506T123333)

- Total questions: **20**
- Answer-expected: 15
- Abstain-expected: 5

## Aggregate metrics

### On answer-expected questions
- **Answered rate**: 100.0% (system did not abstain when it shouldn't have)
- **Cited anything**: 100.0%
- **Cited expected source**: 100.0%
- **Avg keyword recall**: 96.1%

### On abstention-expected questions
- **Abstain precision**: 100.0% (correctly refused)

### Latency
- p50: **1337 ms**
- p95: **10491 ms**

## Per-question breakdown

| id | type | abstained | cited expected | recall | latency |
|----|------|-----------|----------------|--------|---------|
| `pto-days` | answer | no | ✓ | 1.00 | 19137 ms |
| `pto-carryover` | answer | no | ✓ | 1.00 | 1709 ms |
| `sick-days` | answer | no | ✓ | 1.00 | 1222 ms |
| `parental-leave` | answer | no | ✓ | 1.00 | 1346 ms |
| `remote-days` | answer | no | ✓ | 1.00 | 1140 ms |
| `bereavement-days` | answer | no | ✓ | 1.00 | 3035 ms |
| `password-length` | answer | no | ✓ | 1.00 | 1211 ms |
| `password-rotation` | answer | no | ✓ | 1.00 | 1021 ms |
| `mfa-required` | answer | no | ✓ | 1.00 | 1130 ms |
| `vpn-client` | answer | no | ✓ | 1.00 | 1337 ms |
| `incident-report-window` | answer | no | ✓ | 1.00 | 1026 ms |
| `data-classification-levels` | answer | no | ✓ | 1.00 | 1433 ms |
| `sev1-response` | answer | no | ✓ | 0.67 | 1013 ms |
| `sev2-resolution` | answer | no | ✓ | 0.75 | 1033 ms |
| `ticket-lifecycle-stages` | answer | no | ✓ | 1.00 | 1345 ms |
| `abstain-ceo-salary` | abstain | yes | · | 0.00 | 992 ms |
| `abstain-holiday-party` | abstain | yes | · | 0.00 | 1394 ms |
| `abstain-wifi-password` | abstain | yes | · | 0.00 | 10491 ms |
| `abstain-marketing-head` | abstain | yes | · | 0.00 | 1057 ms |
| `abstain-stock-ticker` | abstain | yes | · | 0.00 | 1363 ms |

## Sample answers

### `pto-days` — How many PTO days do full-time employees get per year?
> Full-time employees are entitled to fifteen (15) days of paid time off per calendar year [c_0].

### `pto-carryover` — What is the maximum number of unused PTO days that can be carried over to the next year?
> The maximum number of unused PTO days that can be carried over to the next year is five (5) days [c_0]. Any balance above that cap is forfeited on January 1st [c_0].

### `sick-days` — How many sick days are employees entitled to?
> Employees receive ten (10) days of paid sick leave per year [c_0].

### `parental-leave` — How long is the paid parental leave?
> Eligible employees are entitled to twelve (12) weeks of fully paid parental leave following the birth or adoption of a child [c_0]. Eligibility begins after ninety (90) days of employment [c_0].

### `remote-days` — How many days per week can employees work remotely?
> Employees may work remotely up to three (3) days per week with manager approval [c_0]. Fully remote arrangements require additional approval from the department head and HR [c_0].

