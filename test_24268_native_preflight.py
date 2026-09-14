from types import SimpleNamespace
import pytest
from war3_native_preflight import classify_entry

def region(**kw):
    fields=dict(allocation=0x100000, base=0x110000, size=0x1000,
                state=0x1000, type=0x40000, protect=0x20)
    fields.update(kw)
    return SimpleNamespace(**fields)

def check(r, allow=False, address=0x110010):
    return classify_entry(address, 0x100000, [(0x110000,0x111000)], r, allow)

@pytest.mark.parametrize('protect',[0x20,0x40,0x80])
def test_executable_mapping(protect):
    assert check(region(protect=protect)) == 'readable-executable'

def test_noaccess_requires_explicit_diagnostic():
    with pytest.raises(ValueError): check(region(protect=1))
    assert check(region(protect=1),True) == 'image-noaccess-diagnostic-only'

@pytest.mark.parametrize('protect',[0,2,4,8,0x10,0x101,0x120,0x201])
def test_other_protections_never_bypassed(protect):
    with pytest.raises(ValueError): check(region(protect=protect),True)

@pytest.mark.parametrize('kw',[dict(allocation=0x200000),dict(state=0x2000),
    dict(type=0x20000),dict(base=0x110020),dict(size=20)])
def test_wrong_image_or_region_rejected(kw):
    with pytest.raises(ValueError): check(region(**kw),True)

@pytest.mark.parametrize('address',[0x100000,0x10fff8,0x110ff8,0x111000])
def test_noncode_and_boundary_crossing_rejected(address):
    with pytest.raises(ValueError): check(region(),True,address)
