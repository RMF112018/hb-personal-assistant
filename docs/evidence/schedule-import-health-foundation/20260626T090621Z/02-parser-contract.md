# Parser Contract

## Package DTOs

Added parser-neutral DTOs:

- `ParsedScheduleFile`
- `ParsedScheduleEntity`
- `ParsedSchedulePackage`

`ParsedScheduleBundle` remains for compatibility.

## P6 XML

`parse_pmxml_package_bytes` preserves separate entities:

- `Project` becomes current schedule entity.
- `BaselineProject` becomes baseline schedule entity.
- Baseline rows are not appended to current activities.
- Nested `Activity/UDF` elements are captured.

For legacy XML without baselines, the existing flat parser remains the compatibility path.

## XER

XER parsing now records parser coverage in `schedule_options["parser_coverage"]`, including tables present, fields present, and baseline reference fields. XER baseline reference is treated as reference-only unless baseline activity rows are available from another source.
