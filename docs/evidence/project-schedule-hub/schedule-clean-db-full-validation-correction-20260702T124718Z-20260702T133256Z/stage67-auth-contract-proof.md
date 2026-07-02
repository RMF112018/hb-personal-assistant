# Stage 6/7 auth contract proof

- read header: `X-HB-UI-Role: viewer`
- write header: `X-HB-UI-Role: operator`
- expected viewer mutation failure: `403 operator_role_required` => classification `role_gate_proven`
- `422` before role gate => `route_contract_changed`
- `401 unauthorized` => `auth_not_established` / capture failure (wrong surface, not analytics role gate)
