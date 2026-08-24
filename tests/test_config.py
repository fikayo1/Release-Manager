import pytest
from src.config import Settings
def test_required_and_redacted():
 with pytest.raises(ValueError): Settings("","repo","token")
 cfg=Settings("o","r","super-secret")
 assert "super-secret" not in repr(cfg) and cfg.slug=="o/r"
