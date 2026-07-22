sion','created_at'],
    'properties':{
        'schema_version':{'const':2},'review_id':{'type':'string','minLength':1},'goal_id':{'type':'string','minLength':1},'checkpoint_id':{'type':'string','minLength':1},
        'review_type':{'enum':['PLAN_REVIEW','IMPLEMENTATION_AUDIT','CORRECTIVE_REVIEW','MERGE_READINESS','POST_MERGE_CLOSEOUT']},'reviewer_context':{'const':'independent'},
        'repository':{'type':'object','required':['remote','branch','worktree_mode','worktree_id','base_sha','reviewed_head_sha','pull_request'],'properties':{
            'remote':{'type':'string','minLength':1},'branch':{'type':'string','minLength':1},'worktree_mode':{'enum':['local','remote_only','not_applicable']},'worktree_id':{'type':['string','null']},'base_sha':{'type':'string','pattern':HEX40},'reviewed_head_sha':{'type':'string','pattern':HEX40},'pull_request':{'type':['integer','null'],'minimum':1}},'additionalProperties':False},
        'reviewed_artifacts':{'type':'array','items':{'type':'string'},'uniqueItems':True},'evidence_reviewed':{'type':'array','items':{'type':'string'},'uniqueItems':True},
        'review_disposition':{'enum':['APPROVE','APPROVE_WITH_REQUIRED_CHANGES','REVISE','REJECT','INSUFFICIENT_EVIDENCE','PASS','PASS_WITH_NON_BLOCKING_FINDINGS','FAIL_BLOCKERS_REMAIN','READY_TO_MERGE','READY_WITH_REQUIRED_CONDITIONS','NOT_READY']},
        'required_changes':{'type':'array','items':{'type':'string'}},'recommendations':{'type':'array','items':{'type':'string'}},'findings':{'type':'array','items':{'type':'string'}},'limitations':{'type':'array','items':{'type':'string'}},
        'stale_on_head_change':{'const':True},'operator_decision':{'enum':['PENDING','ACCEPTED','REJECTED','REVISE']},'created_at':{'type':'string','format':'date-time'},
    }
}

finding_schema = {
    '$schema':'https://json-schema.org/draft/2020-12/schema','title':'AEOS Finding Ledger v2','type':'object','additionalProperties':False,
    'required':['schema_version','goal_id','audit_id','findings'],'properties':{
        'schema_version':{'const':2},'goal_id':{'type':'string','minLength':1},'audit_id':{'type':'string','minLength':1},
        'findings':{'type':'array','items':{'type':'object','additionalProperties':False,'required':['finding_id','title','severity','status','original_statement','evidence','affected_acceptance_criteria','authorized_for_correction','disposition_history'],
            'properties':{'finding_id':{'type':'string','minLength':1},'title':{'type':'string','minLength':1},'severity':{'enum':['CRITICAL','HIGH','MEDIUM','LOW','INFORMATIONAL']},'status':{'enum':['OPEN','FIX_CLAIMED','VERIFIED_FIXED','DEFERRED_WITH_ACCEPTED_RISK','REJECTED_WITH_RATIONALE','NOT_REPRODUCIBLE']},'original_statement':{'type':'string'},'evidence':{'type':'array','items':{'type':'string'}},'affected_acceptance_criteria':{'type':'array','items':{'type':'string'}},'authorized_for_correction':{'type':'boolean'},'disposition_history':{'type':'array','items':{'type':'string'}}}}},
    }
}

governance_manifest_schema = {
    '$schema':'https://json-schema.org/draft/2020-12/schema','title':'AEOS Governance Manifest v2','type':'object','additionalProperties':False,
    'required':['schema_version','goal_id','repository','governing_sources','truth_precedence','action_authority','prohibited_without_explicit_authorization'],
    'properties':{
        'schema_version':{'const':2},'goal_id':{'type':'string','minLength':1},'repository':REPOSITORY,
        'governing_sources':{'type':'array','items':{'type':'string'},'minItems':1,'uniqueItems':True},
        'truth_precedence':{'type':'array','items':{'type':'string'},'minItems':1,'uniqueItems':True},
        'action_authority':{'type':'object','required':['operator_controls_scope','access_is_not_authority','publication_is_not_authority','risk_acceptance_is_operator_only'],'properties':{k:{'const':True} for k in ['operator_controls_scope','access_is_not_authority','publication_is_not_authority','risk_acceptance_is_operator_only']},'additionalProperties':False},
        'prohibited_without_explicit_authorization':{'type':'array','items':{'type':'string'},'minItems':1,'uniqueItems':True},
    }
}

work_item_schema = {
    '$schema':'https://json-schema.org/draft/2020-12/schema','title':'AEOS Work Item Ledger v2','type':'object','additionalProperties':False,
    'required':['schema_version','goal_id','work_items'],'properties':{
        'schema_version':{'const':2},'goal_id':{'type':'string','minLength':1},
        'work_items':{'type':'array','items':{'type':'object','additionalProperties':False,'required':['work_item_id','title','status','authorization_id','repository','prerequisites','scope','out_of_scope','acceptance_criteria','required_tests','required_evidence','evidence_representation_requirements','retry_limit','stop_conditions','expected_closeout_disposition','disposition','closeout_receipt'],
            'properties':{'work_item_id':{'type':'string','minLength':1},'title':{'type':'string','minLength':1},'status':{'enum':['PROPOSED','AUTHORIZED','IN_PROGRESS','READY_FOR_REVIEW','BLOCKED','COMPLETE','MERGED_PENDING_CLEANUP','CLOSED']},'authorization_id':{'type':['string','null']},'repository':REPOSITORY,'prerequisites':{'type':'array','items':{'type':'string'}},'scope':{'type':'array','items':{'type':'string'}},'out_of_scope':{'type':'array','items':{'type':'string'}},'acceptance_criteria':{'type':'array','items':{'type':'string'}},'required_tests':{'type':'array','items':{'type':'string'}},'required_evidence':{'type':'array','items':{'type':'string'}},'evidence_representation_requirements':{'type':'array','items':{'type':'string'}},'retry_limit':{'type':'integer','minimum':0},'stop_conditions':{'type':'array','items':{'type':'string'}},'expected_closeout_disposition':{'enum':[None,'REMOVE_AFTER_MERGE','RETAIN','BLOCKED']},'disposition':{'type':['string','null']},'closeout_receipt':{'type':['string','null']}}}},
    }
}

schema_map = {
    'state.schema.json':state_schema,
    'checkpoint-request.schema.json':checkpoint_schema,
    'evidence-index.schema.json':evidence_schema,
    'authorization.schema.json':authorization_schema,
    'external-review.schema.json':external_review_schema,
    'finding-ledger.schema.json':finding_schema,
    'governance-manifest.schema.json':governance_manifest_schema,
    'work-item-ledger.schema.json':work_item_schema,
}
for name, schema in schema_map.items():
    for base in [OUT / '.ai/schemas/goal-loop', OUT / '.ai/agent-skills/_aeos-shared/schemas']:
        base.mkdir(parents=True, exist_ok=True)
        (base / name).write_text(json.dumps(schema, indent=2, sort_keys=False) + '\n', encoding='utf-8')

# Bounded legacy v1 schemas: separate read-only path, never canonical.
legacy_names = ['state.schema.json','checkpoint-request.schema.json','evidence-index.schema.json']
for name in legacy_names:
    legacy = json.loads((CURRENT / '.ai/schemas/goal-loop' / name).read_text(encoding='utf-8'))
    legacy['$id'] = f'https://aeos.local/schemas/goal-loop/legacy-v1/{name}'
    legacy['title'] = legacy.get('title','AEOS Legacy') + ' — LEGACY V1 READ ONLY'
    for base in [OUT / '.ai/schemas/goal-loop/legacy-v1', OUT / '.ai/agent-skills/_aeos-shared/schemas/legacy-v1']:
        base.mkdir(parents=True, exist_ok=True)
        (base / name).write_text(json.dumps(legacy, indent=2) + '\n', encoding='utf-8')
legacy_readme = '''# Legacy Goal-Loop Schema v1 Compatibility\n\nThese schemas are read-only compatibility artifacts. Canonical templates and\nnew goal records MUST use schema version 2. A version 1 record is admissible only\nwhen it is stored under `.ai/aeos/legacy-v1/` and its path and SHA-256 are listed\nin `.ai/aeos/legacy-v1/registry.json`. Empty registry means no legacy record is\ncurrently authenticated.\n'''
for base in [OUT / '.ai/schemas/goal-loop/legacy-v1', OUT / '.ai/agent-skills/_aeos-shared/schemas/legacy-v1']:
    (base / 'README.md').write_text(legacy_readme, encoding='utf-8')
legacy_registry = {'schema_version':1,'allowed_records':[]}
reg_path = OUT / '.ai/aeos/legacy-v1/registry.json'
reg_path.parent.mkdir(parents=True, exist_ok=True)
reg_path.write_text(json.dumps(legacy_registry, indent=2) + '\n', encoding='utf-8')

# Canonical valid templates.
Z='0'*40; O='1'*40; H='a'*64
repo = {'remote':'https://github.com/owner/repository.git','default_branch':'main','base_sha':Z,'head_sha':O,'branch':'chore/replace-me','worktree_mode':'remote_only','worktree_id':None,'worktree_path':None,'pull_request':123}
state = {'schema_version':2,'goal_id':'GOAL-REPLACE-ME','state':'GOVERNANCE_INITIALIZATION','status':'NOT_STARTED','iteration':0,'repository':repo,'lifecycle':{'merge_status':'NOT_MERGED','post_merge_validation':'NOT_APPLICABLE','cleanup_disposition':'NOT_APPLICABLE','closure_status':'OPEN'},'review':{'review_id':None,'reviewed_head_sha':None,'disposition':None,'stale_on_head_change':True},'authorization':{'required':True,'authorization_id':None,'authorized_state':None,'authorized_action':None,'authorized_identity':None,'artifact_hash':None,'expires_on_repository_drift':True},'current_work_item':None,'expected_artifacts':[],'last_checkpoint':None,'requested_next_state':None,'updated_at':'2026-01-01T00:00:00Z'}
checkpoint = {'schema_version':2,'checkpoint_id':'GATE-REPLACE-ME','goal_id':'GOAL-REPLACE-ME','current_state':'GOVERNANCE_INITIALIZATION','state_status':'READY_FOR_REVIEW','disposition':'READY_FOR_EXTERNAL_REVIEW','repository':repo,'lifecycle':state['lifecycle'],'artifacts':[],'claims':{'verified':[],'claimed_not_verified':[],'assumptions':[],'unknowns':[],'unavailable':[]},'test_failures':[],'deviations':[],'unresolved_findings':[],'closeout_receipts':[],'requested_next_state':None,'operator_action_required':True,'created_at':'2026-01-01T00:00:00Z'}
evidence = {'schema_version':2,'goal_id':'GOAL-REPLACE-ME','work_item_id':None,'checkpoint_id':'GATE-REPLACE-ME','repository':repo,'environment':'replace-me','evidence':[{'evidence_id':'EVID-001','path':'relative/path','kind':'test_result','representation':'raw_file','mime_type':'text/plain','hash_scope':'stored_raw_bytes','sha256':H,'source_relation':'direct','claim_ids':['CLAIM-001'],'generated_by':'replace-me','repository_head':O,'environment':'replace-me','verification':'verified','status':'complete'}],'limitations':[],'generated_at':'2026-01-01T00:00:00Z'}
authorization = {'schema_version':2,'authorization_id':'AUTH-REPLACE-ME','goal_id':'GOAL-REPLACE-ME','checkpoint_id':'GATE-REPLACE-ME','authorized_transition':{'from':'GOVERNANCE_INITIALIZATION','to':'REPOSITORY_TRUTH'},'authorized_action':'establish_repository_truth','authorized_work_items':[],'required_changes':[],'constraints':[],'prohibited_actions':['merge'],'repository':repo,'authorized_identity':{'artifact_paths':[],'artifact_hashes':[]},'cleanup_actions':{'worktree_removal':False,'local_branch_deletion':False,'remote_branch_deletion':False,'worktree_metadata_pruning':False,'remote_reference_pruning':False},'expires_on_repository_drift':True,'issued_by':'operator','issued_at':'2026-01-01T00:00:00Z','expires_at':None}
external_review = {'schema_version':2,'review_id':'REVIEW-REPLACE-ME','goal_id':'GOAL-REPLACE-ME','checkpoint_id':'GATE-REPLACE-ME','review_type':'IMPLEMENTATION_AUDIT','reviewer_context':'independent','repository':{'remote':repo['remote'],'branch':repo['branch'],'worktree_mode':'remote_only','worktree_id':None,'base_sha':Z,'reviewed_head_sha':O,'pull_request':123},'reviewed_artifacts':[],'evidence_reviewed':[],'review_disposition':'REVISE','required_changes':[],'recommendations':[],'findings':[],'limitations':[],'stale_on_head_change':True,'operator_decision':'PENDING','created_at':'2026-01-01T00:00:00Z'}
finding = {'schema_version':2,'goal_id':'GOAL-REPLACE-ME','audit_id':'AUDIT-REPLACE-ME','findings':[{'finding_id':'FIND-001','title':'Replace me','severity':'MEDIUM','status':'OPEN','original_statement':'','evidence':[],'affected_acceptance_criteria':[],'authorized_for_correction':False,'disposition_history':[]}]}
gov = {'schema_version':2,'goal_id':'GOAL-REPLACE-ME','repository':repo,'governing_sources':['AGENTS.md','.ai/project-sources/00_AEOS_MASTER_INDEX.md'],'truth_precedence':['runtime_evidence','repository_and_github_state','repository_governance','aeos_standards'],'action_authority':{'operator_controls_scope':True,'access_is_not_authority':True,'publication_is_not_authority':True,'risk_acceptance_is_operator_only':True},'prohibited_without_explicit_authorization':['merge','cleanup','deployment','risk_acceptance']}
work = {'schema_version':2,'goal_id':'GOAL-REPLACE-ME','work_items':[{'work_item_id':'WP-001','title':'Replace me','status':'PROPOSED','authorization_id':None,'repository':repo,'prerequisites':[],'scope':[],'out_of_scope':[],'acceptance_criteria':[],'required_tests':[],'required_evidence':[],'evidence_representation_requirements':[],'retry_limit':3,'stop_conditions':[],'expected_closeout_disposition':None,'disposition':None,'closeout_receipt':None}]}

de