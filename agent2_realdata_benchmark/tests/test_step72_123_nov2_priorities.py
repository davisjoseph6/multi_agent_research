"""Original closure-register fields are the only authority for credit."""
import csv
from pathlib import Path
import pytest
from scripts.step72_123_nov2_priorities import audit,markdown,CREDIT


def register(tmp_path):
    path=tmp_path/'register.csv'
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['step','requirement','evidence_status','evidence_credit','exit_criterion','independent_signoff'])
        w.writeheader()
        for i in range(72,124):
            status='PARTIAL' if i in (72,73,95,106) else 'SYNTHETIC-IMPLEMENTED'
            w.writerow({'step':i,'requirement':f'original {i}','evidence_status':status,
                        'evidence_credit':CREDIT[status],'exit_criterion':f'Exact criterion {i}',
                        'independent_signoff':'NOT RECEIVED'})
    return path


def test_read_only_audit(tmp_path):
    p=register(tmp_path)
    before=p.read_bytes()
    report=audit(p)
    assert p.read_bytes()==before
    assert report['denominator_steps']==52
    assert report['score_proxy_points']==50.
    assert report['scientific_completion_certified'] is False
    assert 'Exact criterion 95' in markdown(report)


def test_reject_register_with_missing_step(tmp_path):
    p=register(tmp_path)
    lines=p.read_text().splitlines();p.write_text('\n'.join(lines[:-1])+'\n')
    with pytest.raises(ValueError,match='exactly Steps'):audit(p)


def test_reject_credit_fraud(tmp_path):
    p=register(tmp_path)
    p.write_text(p.read_text().replace('72,original 72,PARTIAL,0.5','72,original 72,PARTIAL,1.0'))
    with pytest.raises(ValueError,match='Nonstandard'):audit(p)


def test_external_not_auto_closed(tmp_path):
    p=register(tmp_path)
    text=p.read_text().replace('95,original 95,PARTIAL,0.5','95,original 95,EXTERNAL-REQUIRED,0.0')
    p.write_text(text)
    report=audit(p)
    assert report['score_proxy_points']==49.5
    assert report['status_counts']['EXTERNAL-REQUIRED']==1


def test_warn_about_unverified_synthetic_credits(tmp_path):
    report=audit(register(tmp_path))
    assert len(report['synthetic_implemented_rows_without_signoff'])==48
    assert 'synthetic-credit rows with missing signoff' in markdown(report)
