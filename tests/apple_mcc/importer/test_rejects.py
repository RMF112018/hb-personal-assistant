import pytest
from hb_assistant.apple_mcc.importer.validate import ValidationError, validate_item

def test_reject_missing_domain():
    with pytest.raises(ValidationError):
        validate_item({"payload_hash": "x", "observed_at_utc": "t"})
