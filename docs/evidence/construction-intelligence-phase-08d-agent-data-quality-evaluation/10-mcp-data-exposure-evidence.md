# 10 Mcp Data Exposure Evidence

This file is part of an evaluation evidence packet. It records measurable evidence only and does not conclude that the underlying data is usable, meaningful, high quality, or production-ready.

## Machine-Readable Summary

```json
{
  "cli_help_surfaces_checked": [
    {
      "command": ".venv/bin/hb-assistant second-brain mcp tools --help",
      "exit_code": 0,
      "stderr_lines": 0,
      "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "stdout_lines": 15,
      "stdout_sha256": "03a39040b9db6059881c461034f391155cf38249ab175852b7d710b581c6ad27"
    },
    {
      "command": ".venv/bin/hb-assistant second-brain mcp resources --help",
      "exit_code": 0,
      "stderr_lines": 0,
      "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "stdout_lines": 15,
      "stdout_sha256": "f49047066daf2a2daca8c270c64c3502a35d1fa052d6bd677c08164d72b50656"
    },
    {
      "command": ".venv/bin/hb-assistant second-brain mcp prompts --help",
      "exit_code": 0,
      "stderr_lines": 0,
      "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "stdout_lines": 15,
      "stdout_sha256": "d41d37953617bd08071bdc1d087578b0c5d1bc8adcb1ab64a69455357eb2f5bd"
    },
    {
      "command": ".venv/bin/hb-assistant second-brain mcp no-raw-access --help",
      "exit_code": 0,
      "stderr_lines": 0,
      "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "stdout_lines": 14,
      "stdout_sha256": "4b7e037c25ba8efc2d905b66eb43f5d4a5de2a745d71e17fbd27c42bccac73f3"
    },
    {
      "command": ".venv/bin/hb-assistant second-brain mcp no-writeback --help",
      "exit_code": 0,
      "stderr_lines": 0,
      "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "stdout_lines": 15,
      "stdout_sha256": "c6f55c8ae215944659544273b538412312d748107608eb66dd40c7da72cb3dd9"
    },
    {
      "command": ".venv/bin/hb-assistant second-brain data-quality phase-08d-gates --help",
      "exit_code": 0,
      "stderr_lines": 0,
      "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "stdout_lines": 22,
      "stdout_sha256": "90a64baa9d312524ac5caabb27820459ef6d369da3973e0d186eb1d217673d82"
    }
  ],
  "mcp_content_exposure_evaluated_from_registry_and_proof_metadata": true,
  "phase_08d_contract_inventory": {
    "phase_08d_data_quality_gates_contract.json": {
      "sha256": "51d445cc9cedb5aed5c02a44dce733d219b1ddfb0d7a9d7f2edc5e4af92b2ef6",
      "top_level_keys": [
        "contract_name",
        "readiness_overstatement_forbidden",
        "required_gates",
        "statuses",
        "version"
      ]
    },
    "phase_08d_mcp_allowed_tools_contract.json": {
      "sha256": "637dfe754b441115e51dbf7091a911aafc5dc4969fb6f0ac41a3c7430839b329",
      "top_level_keys": [
        "contract_name",
        "global_requirements",
        "tools",
        "version"
      ]
    },
    "phase_08d_mcp_denial_receipt_contract.json": {
      "sha256": "bc1e93648071ab220279a94c1b21e40abdb0e97f4d59b292c2b375a89d8a360f",
      "top_level_keys": [
        "contract_name",
        "forbidden_fields",
        "metadata_only",
        "required_fields",
        "version"
      ]
    },
    "phase_08d_mcp_denied_tools_contract.json": {
      "sha256": "6878907da52fafe825c12fbc57db686ddb1d03a46e08d93c89445ecbc1b295a9",
      "top_level_keys": [
        "contract_name",
        "denial_receipt_required",
        "denied_actions",
        "raw_requested_content_must_not_be_persisted",
        "version"
      ]
    },
    "phase_08d_mcp_permission_audit_contract.json": {
      "sha256": "42d890df7669bf1d6b2e62ad48b7a37346e08eee65adf89f621cf72119b92646",
      "top_level_keys": [
        "checks",
        "contract_name",
        "version"
      ]
    },
    "phase_08d_mcp_prompts_contract.json": {
      "sha256": "501b0577835debb62b771dc5339d82ad289e5763ea1fae672a87ac66e20bb9eb",
      "top_level_keys": [
        "contract_name",
        "prompts",
        "requirements",
        "version"
      ]
    },
    "phase_08d_mcp_resources_contract.json": {
      "sha256": "ccaaf7fdfa8af7e0964bcb1d4a98de52827442a5243f8dd444e9da4df5d3d70d",
      "top_level_keys": [
        "contract_name",
        "requirements",
        "resources",
        "version"
      ]
    },
    "phase_08d_mcp_server_config_contract.json": {
      "sha256": "18a7aa2ab199297a8ba1c4a8f09351546b8e7bf38462361a4045d76d2ade6e1b",
      "top_level_keys": [
        "contract_name",
        "local_only",
        "no_external_network_from_mcp_layer",
        "phase",
        "startup_fail_closed_on",
        "transport_allowed",
        "transport_denied",
        "version"
      ]
    },
    "phase_08d_mcp_tool_call_receipt_contract.json": {
      "sha256": "6f6cd437cd76e30ad9a85c4bbab5d67d1d9a22404eb64d3d77bcd4a55bdca7b8",
      "top_level_keys": [
        "allowed_fields",
        "contract_name",
        "forbidden_fields",
        "metadata_only",
        "version"
      ]
    },
    "phase_08d_validation_matrix.json": {
      "sha256": "bb53468317e2698818853e5b6b00c3c1c4f2a2582648993eac77ef387c6e6d03",
      "top_level_keys": [
        "commands",
        "contract_name",
        "version"
      ]
    }
  },
  "unsafe_mcp_calls_executed": false
}
```
