"""Read-only semantic risk audit of draft Behavioral Economics learning instruments.

Do not mistake a mechanically complete MCQ bank for validated parallel forms.
Results are REVIEW FLAGS, not expert judgments or automatic approvals.
"""
from __future__ import annotations
import argparse
import csv
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from hashlib import sha256
import json
from pathlib import Path
import re

EXPECTED_FORMS = {'pretest': 16, 'posttest': 16, 'practice': 55, 'recovery_drop2': 8}
FIELDS = {'item_id', 'form', 'concept', 'bloom', 'prompt', 'option_A', 'option_B', 'option_C', 'option_D',
          'correct_option_id', 'rationale', 'source_citation', 'review_decision', 'reviewer_record', 'review_date'}
RESOURCE_FIELDS = {'resource_id', 'concept', 'action', 'resource_text', 'review_decision', 'reviewer_record', 'review_date'}
PRE_POST = {'pretest', 'posttest'}


def normalize(value: str) -> str:
    return ' '.join(re.findall(r"[\w]+", value.casefold(), flags=re.UNICODE))


def read_csv(path: Path, required: set[str]) -> list[dict]:
    with path.open('r', encoding='utf-8-sig', newline='') as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f'Unexpected/missing CSV columns in {path}')
        data = list(reader)
    if any(None in row for row in data):
        raise ValueError(f'Unexpected extra CSV columns in {path}')
    return data


def content_signature(row: dict) -> tuple:
    return tuple(sorted(normalize(row[f'option_{letter}']) for letter in 'ABCD'
                        if row[f'option_{letter}'].strip()))


def assess(items: list[dict], resources: list[dict], *, threshold: float = 0.86) -> dict:
    if len(items) != 95 or len(resources) != 32:
        raise ValueError('Expected original 95 item / 32 resource blueprint')
    if type(threshold) is not float or not 0.5 <= threshold <= 1.0:
        raise ValueError('Invalid similarity threshold')
    flags=[]
    def flag(severity, code, ids, explanation):
        flags.append({'severity':severity,'code':code,'ids':sorted(ids),'detail':explanation})
    ids=[r['item_id'] for r in items]
    rids=[r['resource_id'] for r in resources]
    if len(set(ids))!=95 or len(set(rids))!=32:
        raise ValueError('Duplicate source item or resource IDs')
    counts=Counter(r['form'] for r in items)
    if counts != Counter(EXPECTED_FORMS):
        flag('blocking','wrong_form_counts',[],str(dict(counts)))
    blank_fields=0
    for r in items:
        choices={k:r[f'option_{k}'].strip() for k in 'ABCD' if r[f'option_{k}'].strip()}
        if not r['prompt'].strip() or r['correct_option_id'] not in choices or not r['rationale'].strip():
            blank_fields+=1
            flag('blocking','missing_or_invalid_content',[r['item_id']], 'Missing prompt, answer or rationale')
        if len(choices)!=(2 if r['form']=='recovery_drop2' else 4):
            flag('blocking','wrong_number_of_choices',[r['item_id']],f'{len(choices)} choices')
        if len({normalize(x) for x in choices.values()})!=len(choices):
            flag('blocking','duplicate_choices',[r['item_id']],'Duplicate normalized choices')
        if normalize(r['rationale'])==normalize(r['prompt']):
            flag('review','rationale_repeats_prompt',[r['item_id']],'Rationale does not add an explanation')
        if r['bloom']=='create':
            flag('construct','create_is_multiple_choice',[r['item_id']], 'A multiple-choice item does not measure open-ended creation')
        if r['review_decision']!='pending' or r['reviewer_record'].strip() or r['review_date'].strip():
            flag('audit','review_metadata_present',[r['item_id']], 'Do not infer legitimacy; independently verify supplied approval evidence')
    for r in resources:
        if not r['resource_text'].strip():
            flag('blocking','missing_resource_text',[r['resource_id']], 'No instructional text')
        if r['review_decision']!='pending' or r['reviewer_record'].strip() or r['review_date'].strip():
            flag('audit','resource_review_metadata_present',[r['resource_id']], 'Verify independent approval evidence')
    for i, a in enumerate(items):
        for b in items[i+1:]:
            if normalize(a['prompt'])==normalize(b['prompt']):
                flag('blocking','exact_duplicate_prompt',[a['item_id'],b['item_id']], 'Exactly matching normalized stems')
            if a['concept'] != b['concept'] or a['form']==b['form']:
                continue
            is_prepost = {a['form'],b['form']} == PRE_POST
            sig_equal=content_signature(a)==content_signature(b)
            if sig_equal:
                flag('high' if (is_prepost or (a['form'] in PRE_POST and b['form']=='practice') or (b['form'] in PRE_POST and a['form']=='practice')) else 'review','shared_choice_set', [a['item_id'], b['item_id']],
                     f'{a["form"]} versus {b["form"]}; identical option texts ignoring order')
            if normalize(a['rationale'])==normalize(b['rationale']) and a['rationale'].strip():
                if is_prepost:
                    flag('high','shared_prepost_rationale',[a['item_id'],b['item_id']], 'Pre/post forms share the same rationale verbatim')
            if is_prepost:
                likeness=SequenceMatcher(None,normalize(a['prompt']), normalize(b['prompt'])).ratio()
                if likeness>=threshold:
                    flag('high','similar_prepost_stems',[a['item_id'],b['item_id']],f'Stem similarity {likeness:.3f}')
    by_form=defaultdict(Counter)
    by_concept=defaultdict(lambda:defaultdict(Counter))
    for r in items:
        by_form[r['form']][r['bloom']]+=1
        by_concept[r['concept']][r['form']][r['bloom']]+=1
    pre=by_form['pretest']; post=by_form['posttest']
    if pre!=post:
        flag('high','unmatched_prepost_bloom_blueprints',[],
             f'Pretest Bloom counts {dict(sorted(pre.items()))}; posttest counts {dict(sorted(post.items()))}. Comparability requires review, not raw equality alone.')
    for concept, forms in by_concept.items():
        if forms['pretest'] != forms['posttest']:
            flag('high','unmatched_concept_bloom',[concept],
                 f'Pre {dict(sorted(forms["pretest"].items()))}; post {dict(sorted(forms["posttest"].items()))}')
    keys=Counter(r['correct_option_id'] for r in items if r['form'] != 'recovery_drop2')
    reviews_pending=sum(r['review_decision']=='pending' and not r['reviewer_record'].strip() and not r['review_date'].strip()
                        for r in items+resources)
    return {
        'status':'REVIEW REQUIRED - NOT VALIDATED FOR HUMAN STUDY',
        'read_only':True,'human_study_authorized':False,'independent_expert_approval_verified':False,
        'item_count':len(items),'resource_count':len(resources),'review_pending_count':reviews_pending,
        'form_counts':dict(sorted(counts.items())),
        'bloom_by_form': {k:dict(sorted(v.items())) for k,v in sorted(by_form.items())},
        'answer_key_distribution_four_option_items':dict(sorted(keys.items())),
        'flag_counts':dict(sorted(Counter(x['code'] for x in flags).items())),
        'severity_counts':dict(sorted(Counter(x['severity'] for x in flags).items())),
        'flags':flags,
        'not_examined':['Factual correctness of every key, plausible distractors, pedagogical source alignment',
                        'Empirical validity/difficulty, independent expert review, answer leakage beyond local text overlap',
                        'Copyright, linguistic accessibility, outcomes, psychometric reliability, participant authorization'],
    }


def run(items_path: Path, resources_path: Path, output_path: Path|None=None) -> dict:
    items=read_csv(items_path,FIELDS);resources=read_csv(resources_path,RESOURCE_FIELDS)
    result=assess(items,resources)
    result['item_sha256']=sha256(items_path.read_bytes()).hexdigest()
    result['resource_sha256']=sha256(resources_path.read_bytes()).hexdigest()
    if output_path is not None:
        if output_path.resolve() in (items_path.resolve(),resources_path.resolve()):
            raise ValueError('Refusing to overwrite educational content')
        output_path.parent.mkdir(parents=True,exist_ok=True)
        output_path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return result


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--items',type=Path,default=Path('docs/nov2_content_review_drafts/authored_items_PENDING_REVIEW.csv'))
    p.add_argument('--resources',type=Path,default=Path('docs/nov2_content_review_drafts/authored_resources_PENDING_REVIEW.csv'))
    p.add_argument('--output',type=Path,default=None)
    args=p.parse_args()
    report=run(args.items,args.resources,args.output)
    print(json.dumps({k:v for k,v in report.items() if k!='flags'},indent=2,ensure_ascii=False))
    print('Flagged pairs/rows:',len(report['flags']))
    print('Read-only risk audit: does not imply content validation or review.')


if __name__=='__main__':main()
