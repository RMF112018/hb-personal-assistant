# Evidence — Email + Calendar Full Raw Content Ingestion

## Prompt

`<prompt number and title>`

## Repo state

```text
branch:
head:
schema_head_before:
schema_head_after:
```

## Commands run

```bash
# paste commands only, not raw outputs containing bodies
```

## Results summary

| Gate | Result | Notes |
|---|---:|---|
| schema |  |  |
| fixtures |  |  |
| db-copy validation |  |  |
| no-leak scan |  |  |
| tests |  |  |

## Count / null-rate evidence only

| surface | table | rows | preview_non_null | body_text_non_null | body_html_non_null | source_quality | verdict |
|---|---|---:|---:|---:|---:|---|---|
| email |  |  |  |  |  |  |  |
| calendar |  |  |  |  |  |  |  |

## Source-quality distribution

| source_family | source_quality | rows |
|---|---|---:|
| email |  |  |
| calendar |  |  |

## No-leak proof

Document scan scope and pass/fail only. Do not include raw body text.

```text
scan_paths:
secret_findings:
raw_body_sentinel_findings:
join_url_findings:
verdict:
```

## Notes / limitations

- 
