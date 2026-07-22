RGE_READINESS','MERGE_AUTHORIZATION',
    'MERGED_PENDING_CLEANUP','POST_MERGE_VALIDATION',
    'BRANCH_WORKTREE_CLOSEOUT','BOUNDED_CLOSURE_ASSESSMENT','CLOSED'
]
STATUS_ENUM = [
    'NOT_STARTED','IN_PROGRESS','READY_FOR_REVIEW','REVIEW_BLOCKED','BLOCKED',
    'COMPLETE','CLEANUP_AUTHORIZED','RETAINED','CLEANUP_BLOCKED','CLOSED'
]
LIFECYCLE = {
    'type':'object',
    'required':['merge_status','post_merge_validation','cleanup_disposition','closure_status'],
    'properties':{
        'merge_status':{'enum':['NOT_MERGED','MERGE_AUTHORIZED','MERGED_PENDING_CLEANUP','MERGED']},
        'post_merge_validation':{'enum':['NOT_APPLICABLE','PENDING','COMPLETE','NOT_REQUIRED','BLOCKED']},
        'cleanup_disposition':{'enum':['NOT_APPLICABLE','PENDING','AUTHORIZED','COMPLETE','RETAINED','BLOCKED']},
        'closure_status':{'enum':['OPEN','PENDING','READY','CLOSED','BLOCKED']},
    },
    'additionalProperties':False,
}
REPOSITORY = {
    'type':'object',
    'required':['remote','default_branch','base_sha','head_sha','branch','worktree_mode','worktree_id','worktree_path','pull_request'],
    'properties':{
        'remote':{'type':'string','minLength':1},
        'default_branch':{'type':'string','minLength':1},
        'base_sha':{'type':'string','pattern':HEX40},
        'head_sha':{'type':'string','pattern':HEX40},
        'branch':{'type':'string','minLength':1},
        'worktree_mode':{'enum':['local','remote_only','not_applicable']},
        'worktree_id':{'type':['string','null']},
        'worktree_path':{'type':['string','null']},
        'pull_request':{'type':['integer','null'],'minimum':1},
    },
    'allOf':[
        {'if':{'properties':{'worktree_mode':{'const':'local'}}},
         'then':{'properties':{'worktree_id':{'type':'string','minLength':1},'worktree_path':{'type':'string','minLength':1}}}},
        {'if':{'properties':{'worktree_mode':{'enum':['remote_only','not_applicable']}}},
         'then':{'properties':{'worktree_id':{'type':'null'},'worktree_path':{'type':'null'}}}},
    ],
    'additionalProperties':False,
}

state_schema = {
    '$schema':'https://json-schema.org/draft/2020-12/schema',
    '$id':'https://aeos.local/schemas/goal-loop/state-v2.schema.json',
    'title':'AEOS Goal State v2','type':'object',
    'required':['schema_version','goal_id','state','status','iteration','repository','lifecycle','review','authorization','current_work_item','expected_artifacts','last_checkpoint','requested_next_state','updated_at'],
    'properties':{
        'schema_version':{'const':2},
        'goal_id':{'type':'string','minLength':1},
        'state':{'enum':STATE_ENUM},
        'status':{'enum':STATUS_ENUM},
        'iteration':{'type':'integer','minimum':0},
        'repository':REPOSITORY,
        'lifecycle':LIFECYCLE,
        'review':{
            'type':'object','required':['review_id','reviewed_head_sha','disposition','stale_on_head_change'],
            'properties':{
                'review_id':{'type':['string','null']},
                'reviewed_head_sha':{'oneOf':[{'type':'null'},{'type':'string','pattern':HEX40}]},
                'disposition':{'enum':[None,'APPROVE','APPROVE_WITH_REQUIRED_CHANGES','REVISE','REJECT','INSUFFICIENT_EVIDENCE','PASS','PASS_WITH_NON_BLOCKING_FINDINGS','FAIL_BLOCKERS_REMAIN','READY_TO_MERGE','READY_WITH_REQUIRED_CONDITIONS','NOT_READY']},
                'stale_on_head_change':{'const':True},
            },'additionalProperties':False,
        },
        'authorization':{
            'type':'object','required':['required','authorization_id','authorized_state','authorized_action','authorized_identity','artifact_hash','expires_on_repository_drift'],
            'properties':{
                'required':{'type':'boolean'},
                'authorization_id':{'type':['string','null']},
                'authorized_state':{'oneOf':[{'type':'null'},{'enum':STATE_ENUM}]},
                'authorized_action':{'type':['string','null']},
                'authorized_identity':{
                    'oneOf':[{'type':'null'},{'type':'object','required':['branch','base_sha','head_sha','worktree_mode','worktree_id','worktree_path','pull_request'],
                        'properties':{
                            'branch':{'type':'string','minLength':1},'base_sha':{'type':'string','pattern':HEX40},'head_sha':{'type':'string','pattern':HEX40},
                            'worktree_mode':{'enum':['local','remote_only','not_applicable']},'worktree_id':{'type':['string','null']},'worktree_path':{'type':['string','null']},
                            'pull_request':{'type':['integer','null'],'minimum':1},
                        },'additionalProperties':False}],
                },
                'artifact_hash':{'oneOf':[{'type':'null'},{'type':'string','pattern':HEX64}]},
                'expires_on_repository_drift':{'const':True},
            },'additionalProperties':False,
        },
        'current_work_item':{'type':['string','null']},
        'expected_artifacts':{'type':'array','items':{'type':'string'},'uniqueItems':True},
        'last_checkpoint':{'type':['string','null']},
        'requested_next_state':{'oneOf':[{'type':'null'},{'enum':STATE_ENUM}]},
        'updated_at':{'type':'string','format':'date-time'},
    },
    'additionalProperties':False,
}

checkpoint_schema = {
    '$schema':'https://json-schema.org/draft/2020-12/schema','$id':'https://aeos.local/schemas/goal-loop/checkpoint-v2.schema.json',
    'title':'AEOS Checkpoint Request v2','type':'object',
    'required':['schema_version','checkpoint_id','goal_id','current_state','state_status','disposition','repository','lifecycle','artifacts','claims','test_failures','deviations','unresolved_findings','closeout_receipts','requested_next_state','operator_action_required','created_at'],
    'properties':{
        'schema_version':{'const':2},'checkpoint_id':{'type':'string','minLength':1},'goal_id':{'type':'string','minLength':1},
        'current_state':{'enum':STATE_ENUM},'state_status':{'enum':STATUS_ENUM},
        'disposition':{'enum':['READY_FOR_EXTERNAL_REVIEW','IMPLEMENTATION_COMPLETE_PENDING_AUDIT','CORRECTIVE_WORK_READY_FOR_REAUDIT','READY_FOR_MERGE_REVIEW','MERGED_PENDING_CLEANUP','POST_MERGE_VALIDATION_COMPLETE','CLOSEOUT_READY_FOR_OPERATOR_DECISION','BLOCKED','INSUFFICIENT_EVIDENCE','ENVIRONMENT_INVALID','FAILED_BOUNDED','OPERATOR_AUTHORIZATION_REQUIRED']},
        'repository':REPOSITORY,'lifecycle':LIFECYCLE,
        'artifacts':{'type':'array','items':{'type':'object','required':['path','representation','hash_scope','sha256'],'properties':{
            'path':{'type':'string','minLength':1},'representation':{'type':'string','minLength':1},'hash_scope':{'enum':['stored_raw_bytes','source_bytes','exported_bytes','not_applicable']},
            'sha256':{'oneOf':[{'type':'null'},{'type':'string','pattern':HEX64}]},},'additionalProperties':False}},
        'claims':{'type':'object','required':['verified','claimed_not_verified','assumptions','unknowns','unavailable'],'properties':{k:{'type':'array','items':{'type':'string'},'uniqueItems':True} for k in ['verified','claimed_not_verified','assumptions','unknowns','unavailable']},'additionalProperties':False},
        'test_failures':{'type':'array','items':{'type':'string'},'uniqueItems':True},
        'deviations':{'type':'array','items':{'type':'string'},'uniqueItems':True},
        'unresolved_findings':{'type':'array','items':{'type':'string'},'uniqueItems':True},
        'closeout_receipts':{'type':'array','items':{'type':'string'},'uniqueItems':True},
        'requested_next_state':{'oneOf':[{'type':'null'},{'enum':STATE_ENUM}]},
        'operator_action_required':{'const':True},'created_at':{'type':'string','format':'date-time'},
    },'additionalProperties':False,
}

evidence_item = {
    'type':'object','required':['evidence_id','path','kind','representation','mime_type','hash_scope','sha256','source_relation','claim_ids','generated_by','repository_head','environment','verification','status'],
    'properties':{
        'evidence_id':{'type':'string','minLength':1},'path':{'type':'string','minLength':1},'kind':{'type':'string','minLength':1},
        'representation':{'enum':['raw_file','repository_blob','native_google_doc','exported_representation','runtime_observation','external_object','narrative','unavailable']},
        'mime_type':{'type':['string','null']},'hash_scope':{'enum':['stored_raw_bytes','source_bytes','exported_bytes','not_applicable']},
        'sha256':{'oneOf':[{'type':'null'},{'type':'string','pattern':HEX64}]},
        'source_relation':{'enum':['direct','derived','export_of','source_of','narrative','unavailable']},
        'claim_ids':{'type':'array','items':{'type':'string','minLength':1},'uniqueItems':True},
        'generated_by':{'type':['string','null']},'repository_head':{'type':'string','pattern':HEX40},
        'environment':{'type':['string','object','null']},'verification':{'enum':['verified','claimed_not_verified','not_applicable','unavailable']},
        'status':{'enum':['complete','partial','invalid','unavailable','pending']},
    },
    'allOf':[
        {'if':{'properties':{'hash_scope':{'enum':['stored_raw_bytes','source_bytes','exported_bytes']}}},'then':{'properties':{'sha256':{'type':'string','pattern':HEX64}}}},
        {'if':{'properties':{'hash_scope':{'const':'not_applicable'}}},'then':{'properties':{'sha256':{'type':'null'}}}},
    ],
    'additionalProperties':False,
}

evidence_schema = {
    '$schema':'https://json-schema.org/draft/2020-12/schema','$id':'https://aeos.local/schemas/goal-loop/evidence-v2.schema.json',
    'title':'AEOS Evidence Index v2','type':'object',
    'required':['schema_version','goal_id','work_item_id','checkpoint_id','repository','environment','evidence','limitations','generated_at'],
    'properties':{
        'schema_version':{'const':2},'goal_id':{'type':'string','minLength':1},'work_item_id':{'type':['string','null']},'checkpoint_id':{'type':'string','minLength':1},
        'repository':REPOSITORY,'environment':{'type':['string','object']},'evidence':{'type':'array','minItems':1,'items':evidence_item},
        'limitations':{'type':'array','items':{'type':'string'},'uniqueItems':True},'generated_at':{'type':'string','format':'date-time'},
    },'additionalProperties':False,
}

# Additional strict schemas for every structured template.
authorization_schema = {
    '$schema':'https://json-schema.org/draft/2020-12/schema','title':'AEOS Authorization v2','type':'object','additionalProperties':False,
    'required':['schema_version','authorization_id','goal_id','checkpoint_id','authorized_transition','authorized_action','authorized_work_items','required_changes','constraints','prohibited_actions','repository','authorized_identity','cleanup_actions','expires_on_repository_drift','issued_by','issued_at','expires_at'],
    'properties':{
        'schema_version':{'const':2},'authorization_id':{'type':'string','minLength':1},'goal_id':{'type':'string','minLength':1},'checkpoint_id':{'type':'string','minLength':1},
        'authorized_transition':{'type':'object','required':['from','to'],'properties':{'from':{'enum':STATE_ENUM},'to':{'enum':STATE_ENUM}},'additionalProperties':False},
        'authorized_action':{'type':'string','minLength':1},'authorized_work_items':{'type':'array','items':{'type':'string'},'uniqueItems':True},
        'required_changes':{'type':'array','items':{'type':'string'}},'constraints':{'type':'array','items':{'type':'string'}},'prohibited_actions':{'type':'array','items':{'type':'string'},'uniqueItems':True},
        'repository':REPOSITORY,
        'authorized_identity':{'type':'object','required':['artifact_paths','artifact_hashes'],'properties':{'artifact_paths':{'type':'array','items':{'type':'string'},'uniqueItems':True},'artifact_hashes':{'type':'array','items':{'type':'string','pattern':HEX64},'uniqueItems':True}},'additionalProperties':False},
        'cleanup_actions':{'type':'object','required':['worktree_removal','local_branch_deletion','remote_branch_deletion','worktree_metadata_pruning','remote_reference_pruning'],'properties':{k:{'type':'boolean'} for k in ['worktree_removal','local_branch_deletion','remote_branch_deletion','worktree_metadata_pruning','remote_reference_pruning']},'additionalProperties':False},
        'expires_on_repository_drift':{'const':True},'issued_by':{'type':'string','minLength':1},'issued_at':{'type':'string','format':'date-time'},'expires_at':{'type':['string','null'],'format':'date-time'},
    }
}

external_review_schema = {
    '$schema':'https://json-schema.org/draft/2020-12/schema','title':'AEOS External Review v2','type':'object','additionalProperties':False,
    'required':['schema_version','review_id','goal_id','checkpoint_id','review_type','reviewer_context','repository','reviewed_artifacts','evidence_reviewed','review_disposition','required_changes','recommendations','findings','limitations','stale_on_head_change','operator_deci