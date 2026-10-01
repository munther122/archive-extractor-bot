import pytest
from bot.utils.security import safe_path

def test_safe_path(tmp_path):
    assert safe_path(tmp_path,'a/b.txt').parent==tmp_path/'a'
    with pytest.raises(ValueError): safe_path(tmp_path,'/etc/passwd')
    with pytest.raises(ValueError): safe_path(tmp_path,'../../x')
