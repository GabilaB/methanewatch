import json
import pandas as pd
import pytest
from methanewatch.pipeline import normalize,run

def sample():
    return pd.DataFrame([{'plume_id':'a','datetime':'2025-01-01T00:00:00Z','latitude':1,'longitude':32,'emission':1000},
                         {'plume_id':'a','datetime':'2025-01-01T00:00:00Z','latitude':1,'longitude':32,'emission':1000},
                         {'plume_id':'b','datetime':'invalid','latitude':95,'longitude':33,'emission':100}])

def test_validate():
    out=normalize(sample(),'test',flux_field='emission',flux_unit='kg/h')
    assert out.iloc[0].flux_tph==pytest.approx(1.0)
    assert out.iloc[2].quality_status=='rejected'

def test_flux_requires_units():
    with pytest.raises(ValueError):normalize(sample(),'test',flux_field='emission')

def test_release(tmp_path):
    source=tmp_path/'test.csv';sample().to_csv(source,index=False)
    stats=run(source,'test',tmp_path/'products',flux_field='emission',flux_unit='kg/h')
    assert stats['accepted_rows']==1
    assert stats['rejected_rows']==2
    assert stats['duplicate_rows']==1
    geo=json.loads((tmp_path/'products'/'plumes.geojson').read_text())
    assert len(geo['features'])==1
