#!/usr/bin/env python3
"""Fixed post-step telemetry only. Never emits exception text, paths or settings."""
import hashlib, json, os, re, stat
from pathlib import Path
TASK='tasks/lottery-shop'
SCOPE='POST_CAPTURE_STATUS_ONLY_NOT_NATIVE_OR_ART_OR_SOURCE_APPROVAL'
CODES={'PATH_CHANGED', 'SOURCE_BYTES_LIMIT', 'OBSERVER_OUTPUT', 'OBSERVER_ENVELOPE', 'OBSERVATION_CONTEXT_REJECTED', 'SESSION_NOT_CLOSED', 'STALE_NATIVE_XML_TIME', 'EXTERNAL_ARTIFACT_DIGEST_MISMATCH', 'REPORT_SCHEMA_OR_SOURCE', 'RUN_IDENTITY', 'EXECUTING_CODE_DIFFERS_FROM_REVIEW', 'UNREVIEWED_INPUT', 'UNSAFE_OR_DUPLICATE_ZIP_ENTRY', 'OBSERVATION_BINDING_REJECTED', 'SAFE_WRITE_REJECTED', 'CI_CHECKOUT_MISMATCH', 'SOURCE_BLOB_LIMIT', 'DEPENDENCY_PATH', 'REVIEWED_HELPER_PLAN_VALIDATOR_IDENTITY_MISMATCH', 'SAFE_PHASE_REJECTED', 'PATH_TYPE_OR_LIMIT', 'REAL_GUARD_INPUT_BINDING_MISMATCH', 'SOURCE_COUNT', 'ARTIFACT_BOUND', 'INPUT_OR_DEPENDENCY_REJECTED', 'REVIEWED_DIAGNOSTIC_CODE_MUTATED_OR_MISSING', 'INPUT_DIRECTORY_TYPE', 'CAPTURE_SESSION_WOULD_BE_BLOCKED', 'CI_CONTEXT_REQUIRED', 'PRIVATE_ROOT_LOCATION', 'SAFE_STATUS_REJECTED', 'DIAGNOSTIC_RESTORE_REJECTED', 'PROTECTED_ADAPTER_REQUIRED', 'EXTERNAL_ARTIFACT_ID_REQUIRED', 'NON_PROJECT_SOURCE_DRIFT', 'EXPECTED_WORKFLOW_CONTEXT_REQUIRED', 'LOCAL_VERIFIER_OR_PLAN_VERSION_DRIFT', 'UNREVIEWED_SOURCE_MUTATION', 'ORIGINAL_FIRST_ATTEMPT_ONLY', 'AFTER_STATE_DRIFT', 'MISSING_NATIVE_DIAGNOSTIC_OPT_IN', 'PINNED_DEPENDENCY_CHANGED', 'GATE_PINNED_VALIDATOR_IDENTITY_MISMATCH', 'GUARD_IDENTITY', 'OBSERVATION_PNG_REJECTED', 'OWNED_NATIVE_CLEANUP_UNVERIFIED', 'DIAGNOSTIC_CONTROL_REJECTED', 'GIT_REJECTED', 'DEPENDENCY_LOCK_DRIFT', 'SAFE_IDENTITY_REJECTED', 'CAPTURE_NATIVE_BUDGET', 'NATIVE_COMPILER_OR_LICENSE_FAILURE', 'CLI_ARGUMENTS', 'SETTINGS_FINDINGS_INCONSISTENT', 'JSON_NONFINITE', 'EXTERNAL_CODE_CONTRACT_DIGEST_REQUIRED', 'NATIVE_START_TIME_REQUIRED', 'SAFE_PATH_REJECTED', 'PATH_REPLACED', 'SOURCE_CONTEXT_DRIFT', 'SOURCE_BYTES', 'DEPENDENCY_LOCK', 'RETURN_NATIVE_STATUS', 'OBSERVER_NOT_INCONCLUSIVE', 'EXTERNAL_EXPECTATIONS_REQUIRED', 'SETTINGS_UNKNOWN_LAYOUT', 'UNSAFE_GATE_BINDING', 'DIAGNOSTIC_BASELINE_REJECTED', 'OBSERVATION_SCHEMA_REJECTED', 'CAPTURE_DIAGNOSTIC_SELECTOR', 'JSON_LIMIT', 'DIAGNOSTIC_CONTROL_MUTATION', 'GATE_SCOPE_MISSING', 'DEPENDENCY_RECORD', 'ARTIFACT_ENTRY_BOUND', 'FONT_DRIFT', 'ORIGINAL_NATIVE_BUDGET_CHANGED', 'UPSTREAM_IDENTITY_MISMATCH', 'DIAGNOSTIC_CAMERA_REJECTED', 'GATE_BINDINGS_MISSING', 'INPUT_BYTES_LIMIT', 'OUTPUT_PARENT', 'PRIVATE_STATE_EXISTS', 'JSON_DUPLICATE_KEY', 'OBSERVER_IDENTITY', 'BOUND_EVIDENCE_TAMPERED', 'REPORT_HASH', 'UNBOUND_OR_MISSING_ARTIFACT_FILE', 'STALE_XML_RECEIPT_BINDING', 'CLEANUP_NOT_VERIFIED', 'SETTINGS_LINES', 'NOT_COLD', 'PREPARED_CONTEXT_SCOPE', 'GUARD_RECEIPT_DRIFT', 'NATIVE_WRITER_NOT_PROVEN_ABSENT', 'PROTECTED_CODE_DRIFT', 'CAPTURE_NATIVE_START', 'GIT_READ_BOUND', 'SETTINGS_BASELINE_DRIFT', 'SETTINGS_SENSITIVE_VALUE', 'PATH_ANCESTOR', 'PATH_LIMIT', 'SETTINGS_LINK', 'CODE_CHANGED_AFTER_PREPARE', 'CI_IDENTITY_INVALID', 'LICENSE_RETURN_NOT_SUCCEEDED', 'SETTINGS_ENCODING', 'PS4_BASELINE_NOT_EMPTY', 'BEFORE_HASH_DRIFT', 'NATIVE_PROCESS_FAILED', 'GUARD_SCOPE', 'NATIVE_RECEIPT_SCHEMA', 'ADAPTER_COPY_DRIFT', 'REVIEWED_HELPER_PLAN_OR_VALIDATOR_MISSING_OR_CHANGED', 'NATIVE_RECEIPT_IDENTITY', 'SOURCE_SNAPSHOT_COVERAGE_DRIFT', 'NATIVE_RECEIPT_CONTEXT', 'SOURCE_PATH', 'INPUT_COUNT', 'OUTPUT_READBACK', 'DEPENDENCY_DRIFT', 'LOCAL_VERIFIER_CONTRACT_IS_NOT_REVIEWED_VERSION', 'CAPTURE_NATIVE_STATUS', 'SETTINGS_LINE_LIMIT', 'NATIVE_PROCESS_SCOPE', 'NATIVE_OBSERVATIONS', 'PS4_BEFORE_NOT_EMPTY', 'PNG_REJECTED', 'OBSERVER_EXIT', 'GUARD_REVIEW', 'SESSION_IDENTITY', 'PRIVATE_STATE_MODE', 'CODE_CONTRACT_DIGEST_MISMATCH', 'GUARD_ENV_MISMATCH', 'BUNDLE_OUTPUT_ALREADY_EXISTS', 'EVIDENCE_PATH_REJECTED', 'CODE_CONTRACT_NOT_IN_REVIEWED_SOURCE', 'SETTINGS_FILE_SET', 'DEPENDENCY_MODULE_SHADOWED', 'DIAGNOSTIC_NOT_COMPLETE', 'CODE_CONTRACT_NOT_PREPARED', 'NATIVE_RESULT_FIELDS', 'NATIVE_MECHANISM_DRIFT', 'OBSERVER_REPORT_HASH', 'NON_PROJECT_SOURCE_MISSING', 'DEPENDENCY_COUNT', 'REVIEWED_SOURCE_NOT_APPROVED', 'DEPENDENCY_PINS_CHANGED_AFTER_PREPARE', 'NORMAL_RECEIPT_REWRITE', 'UPSTREAM_NATIVE_RECEIPT_NOT_REPRODUCIBLE'}
CODES |= {'OBSERVER_OUTPUT_REPLACED', 'OBSERVER_BEFORE_SAFE_FIELDS', 'OBSERVER_REFLECTION_META_LIST_REJECTED', 'OBSERVER_REFLECTION_META_PLATFORM_REJECTED', 'OBSERVER_FILE_SIZE', 'OBSERVER_GAME_SOURCE_MISMATCH', 'OBSERVER_BEFORE_CLAIMS', 'OBSERVER_IDENTITY_CONTEXT', 'OBSERVER_REFLECTION_META_SIZE_REJECTED', 'OBSERVER_META_UNSUPPORTED_FLOW', 'OBSERVER_JSON_INVALID', 'OBSERVER_FILE_EXECUTABLE', 'OBSERVER_BEFORE_EXPECTED_HASH', 'OBSERVER_REFLECTION_GUID', 'OBSERVER_RECIPE_NAME', 'OBSERVER_IDENTITY_COMMIT', 'OBSERVER_DIRECTORY_LINK_OR_TYPE', 'OBSERVER_REFLECTION_META_DUPLICATE_KEY', 'OBSERVER_REFLECTION_META_IMPORT_REJECTED', 'OBSERVER_JSON_NONFINITE', 'OBSERVER_BEFORE_RECORD', 'OBSERVER_META_ENCODING_OR_SIZE', 'OBSERVER_REFLECTION_META_FIELD_OR_VALUE_REJECTED', 'OBSERVER_BEFORE_PATHS', 'OBSERVER_BEFORE_PROJECTION_LABEL', 'OBSERVER_MESH_OBSERVATION_LIMIT', 'OBSERVER_CLI_ARGUMENTS', 'OBSERVER_FILE_ALIAS', 'OBSERVER_BEFORE_RECORD_TYPE', 'OBSERVER_UNKNOWN_DIRECTORY', 'OBSERVER_BEFORE_CONTEXT', 'OBSERVER_RECIPE_COLLISION', 'OBSERVER_REFLECTION_META_LINE_REJECTED', 'OBSERVER_META_LINE_SIZE', 'OBSERVER_JSON_TOO_LARGE', 'OBSERVER_META_SIZE', 'OBSERVER_REFLECTION_META_STRUCTURE_REJECTED', 'OBSERVER_OUTPUT_INSIDE_PROJECT', 'OBSERVER_TOTAL_SIZE', 'OBSERVER_META_DUPLICATE_KEY', 'OBSERVER_JSON_DUPLICATE_KEY', 'OBSERVER_IDENTITY_FIELDS', 'OBSERVER_BEFORE_NOT_COLD_SOURCE', 'OBSERVER_BEFORE_FILES', 'OBSERVER_NATIVE_EXIT_INVALID', 'OBSERVER_ANCESTOR_REPLACED', 'OBSERVER_META_UNSUPPORTED_SCALAR', 'OBSERVER_META_SENSITIVE_KEY', 'OBSERVER_PATH_REJECTED', 'OBSERVER_ROOT_NOT_ABSOLUTE', 'OBSERVER_ENTRY_LIMIT', 'OBSERVER_FILE_CHANGED_DURING_READ', 'OBSERVER_FROZEN_SOURCE_MISSING', 'OBSERVER_OUTPUT_LINK_CHANGED', 'OBSERVER_BEFORE_PROJECTION_TAMPERED', 'OBSERVER_REPORT_SIZE', 'OBSERVER_BEFORE_SCHEMA', 'OBSERVER_DIRECTORY_RACE', 'OBSERVER_REFLECTION_META_ROOT_REJECTED', 'OBSERVER_DIRECTORY_CHANGED', 'OBSERVER_BEFORE_HASH', 'OBSERVER_FILE_RACE', 'OBSERVER_FILE_LINK_OR_TYPE', 'OBSERVER_META_SENSITIVE_OR_BUNDLE_VALUE', 'OBSERVER_INPUT_OR_IO_REJECTED', 'OBSERVER_UNKNOWN_PATH', 'OBSERVER_META_UNSUPPORTED_STRUCTURE', 'OBSERVER_POLICY_DRIFT', 'OBSERVER_INPUT_DRIFT', 'OBSERVER_SOURCE_DUPLICATE', 'OBSERVER_PHASE_REJECTED', 'OBSERVER_IDENTITY_RUN', 'OBSERVER_BEFORE_IDENTITY_MISMATCH', 'OBSERVER_META_UNSUPPORTED_SYNTAX', 'OBSERVER_FILE_REPLACED', 'OBSERVER_TRACKED_GUID_CHANGED', 'OBSERVER_DIRECTORY_REPLACED', 'OBSERVER_FROZEN_INPUT_DRIFT', 'OBSERVER_BEFORE_SNAPSHOT_TAMPERED', 'OBSERVER_META_ENCODING'}
# Finite diagnostic alphabet only. None of these labels is copied from input.
META_FLOW_ASSETS = ('MODEL_INTERIOR', 'MODEL_LAMP', 'MODEL_STAMP', 'MODEL_BOX',
                    'SOURCE_PAIRED_META', 'SOURCE_DIRECTORY_META',
                    'GENERATED_DIRECTORY_META', 'GENERATED_ASSET_META',
                    'BOUNDED_MESH_META', 'OTHER_META')
META_FLOW_FIELDS = ('MODEL_EXTERNAL_FIRST', 'MODEL_EXTERNAL_SECOND',
                    'MODEL_INTERNAL_ID_FIRST', 'MODEL_INTERNAL_ID_SECOND',
                    'MODEL_OTHER', 'OTHER')
META_FLOW_SHAPES = ('MATERIAL_CORE_KNOWN', 'MATERIAL_LEGACY_KNOWN',
                    'MATERIAL_CORE_UNKNOWN_NAME', 'TYPED_IDENTIFIER_OTHER',
                    'INTEGER_PAIR_BOUNDED', 'INTEGER_PAIR_OTHER',
                    'RGBA_FINITE_BOUNDED', 'RGBA_OTHER',
                    'REFERENCE_BOUNDED_NONCANONICAL', 'REFERENCE_OTHER',
                    'DUPLICATE_KEYS', 'NESTED_COLLECTION', 'YAML_SPECIAL',
                    'LIMIT', 'OTHER')
META_FLOW_CODES = frozenset('META_UNSUPPORTED_FLOW__' + asset + '__' + field + '__' + shape
                            for asset in META_FLOW_ASSETS for field in META_FLOW_FIELDS
                            for shape in META_FLOW_SHAPES)

CODES |= {'OBSERVER_' + code for code in META_FLOW_CODES}

PHASES={'START','CONTEXT','CONTRACT','PREPARED','INPUT_PATHS','COPY_INPUTS','UPSTREAM_NATIVE','SOURCE_MUTATION','REGRESSION_CAPTURE','REGRESSION_EDIT','REGRESSION_CORE','REGRESSION_WORLD','PLAY_AGGREGATE','NORMAL_CAPTURE','DIAGNOSTIC_VALIDATE','GATE_WRITE','DEPENDENCIES','SOURCE_BASELINE','RECEIPTS','NATIVE_WRITER_ABSENCE','FONT','SETTINGS','WORKSPACE','OBSERVER','REPORT','PUBLISH','DONE'}
MODES={'counter-light':{'prepare','finalize'},'inventory':{'before','after','publish'},'counter-observation':{'export'}}
ACTIVE={}
class SafetyBlocked(ValueError): pass

def require(ok,code):
 if not ok: raise SafetyBlocked(code)

def regular(path,maximum):
 path=Path(path).absolute()
 for p in path.parents: require(stat.S_ISDIR(p.lstat().st_mode),'SAFE_PATH_REJECTED')
 info=path.lstat();require(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_size<=maximum,'SAFE_PATH_REJECTED')
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  got=os.fstat(fd);require((got.st_dev,got.st_ino)==(info.st_dev,info.st_ino),'SAFE_PATH_REJECTED')
  raw=b''
  while len(raw)<=maximum:
   b=os.read(fd,min(65536,maximum+1-len(raw)))
   if not b:break
   raw+=b
  current=path.lstat();final=os.fstat(fd)
  signature=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_nlink,s.st_mode)
  require(len(raw)<=maximum and signature(info)==signature(current)==signature(final),'SAFE_PATH_REJECTED')
  return raw
 finally:os.close(fd)

def identity():
 values={k:os.environ.get(e,'') for k,e in [('sourceCommit','GITHUB_SHA'),('runId','GITHUB_RUN_ID'),('runAttempt','GITHUB_RUN_ATTEMPT')]}
 require(re.fullmatch('[0-9a-f]{40}',values['sourceCommit']) and re.fullmatch('[1-9][0-9]{0,19}',values['runId']) and values['runAttempt']=='1','SAFE_IDENTITY_REJECTED')
 return values

def write_new(path,raw):
 path=Path(path).absolute();require(path.parent.resolve()==path.parent,'SAFE_PATH_REJECTED')
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 require(regular(path,len(raw))==raw,'SAFE_WRITE_REJECTED')

def begin(component,mode):
 require(component in MODES and mode in MODES[component],'SAFE_PHASE_REJECTED')
 ACTIVE.update(component=component,mode=mode,phase='START')

def checkpoint(phase):
 if not ACTIVE:return
 require(phase in PHASES,'SAFE_PHASE_REJECTED');ACTIVE['phase']=phase
 # Each checkpoint replaces a fixed, safe status JSON, so timeout leaves its last phase.
 try:persist('RUNNING','NONE')
 except BaseException:pass

def error_code(error):
 text=str(error)
 if text in CODES:return text
 mapping=[('Missing or symlink','EVIDENCE_PATH_REJECTED'),('MISSING_OR_LINKED_EVIDENCE','EVIDENCE_PATH_REJECTED'),('PNG ','PNG_REJECTED'),('Diagnostic not complete','DIAGNOSTIC_NOT_COMPLETE'),('Experiment contains non-allowlisted','DIAGNOSTIC_CONTROL_MUTATION'),('Camera ','DIAGNOSTIC_CAMERA_REJECTED'),('Initial ','DIAGNOSTIC_BASELINE_REJECTED'),('Case restoration','DIAGNOSTIC_RESTORE_REJECTED'),('Restoration digest','DIAGNOSTIC_RESTORE_REJECTED'),('Control ','DIAGNOSTIC_CONTROL_REJECTED'),('Controls ','DIAGNOSTIC_CONTROL_REJECTED')]
 for prefix,code in mapping:
  if text.startswith(prefix):return code
 return 'INPUT_OR_DEPENDENCY_REJECTED'

def persist(status,code):
 require(status in {'RUNNING','BLOCKED','COMPLETED'} and code in CODES|{'NONE'},'SAFE_STATUS_REJECTED')
 ident=identity();require(ACTIVE.get('phase') in PHASES,'SAFE_PHASE_REJECTED')
 row={'schemaVersion':1,'scope':SCOPE,**ident,**ACTIVE,'status':status,'code':code,'acceptance':'NOT_EVALUATED','identityBasis':'RUNNER_ENVIRONMENT_NOT_INDEPENDENT_ATTESTATION'}
 root=Path(os.environ['GITHUB_WORKSPACE']).absolute();require(root.resolve()==root,'SAFE_PATH_REJECTED')
 directory=root/TASK/'evidence/visual-candidate';require(directory.resolve()==directory,'SAFE_PATH_REJECTED');directory.mkdir(parents=True,exist_ok=True)
 destination=directory/('post-'+ACTIVE['component']+'-'+ACTIVE['mode']+'.json');temporary=directory/(destination.name+'.new')
 raw=(json.dumps(row,sort_keys=True,separators=(',',':'))+'\n').encode()
 if destination.exists():regular(destination,8192)
 write_new(temporary,raw);os.replace(temporary,destination);require(regular(destination,8192)==raw,'SAFE_WRITE_REJECTED')
 return row

def fail(error):
 code=error_code(error)
 try:persist('BLOCKED',code)
 except BaseException:pass
 print(json.dumps({'status':'BLOCKED','code':code,'phase':ACTIVE.get('phase','START') if ACTIVE.get('phase','START') in PHASES else 'START'}))
 return 3

STATUS_TARGETS = {
 'post-counter-light-prepare.json':('counter-light','prepare'),
 'post-counter-light-finalize.json':('counter-light','finalize'),
 'post-counter-observation-export.json':('counter-observation','export'),
 'post-inventory-before.json':('inventory','before'),
 'post-inventory-after.json':('inventory','after'),
 'post-inventory-publish.json':('inventory','publish'),
}
STATUS_KEYS={'schemaVersion','scope','sourceCommit','runId','runAttempt','component','mode','phase','status','code','acceptance','identityBasis'}

def screened_status(raw,name,ident):
 require(name in STATUS_TARGETS and len(raw)<=8192,'SAFE_STATUS_REJECTED')
 def unique(pairs):
  result={}
  for key,value in pairs:
   require(key not in result,'SAFE_STATUS_REJECTED');result[key]=value
  return result
 row=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:require(False,'SAFE_STATUS_REJECTED'))
 require(type(row)is dict and set(row)==STATUS_KEYS,'SAFE_STATUS_REJECTED')
 require(type(row['schemaVersion'])is int and row['schemaVersion']==1 and row['scope']==SCOPE,'SAFE_STATUS_REJECTED')
 require(all(row[k]==value for k,value in ident.items()),'SAFE_IDENTITY_REJECTED')
 require((row['component'],row['mode'])==STATUS_TARGETS[name] and row['phase'] in PHASES,'SAFE_STATUS_REJECTED')
 require(row['status'] in {'RUNNING','COMPLETED','BLOCKED'} and row['code'] in CODES|{'NONE'},'SAFE_STATUS_REJECTED')
 require((row['status']=='BLOCKED')==(row['code']!='NONE'),'SAFE_STATUS_REJECTED')
 require(row['status']!='COMPLETED' or row['phase']=='DONE','SAFE_STATUS_REJECTED')
 require(row['acceptance']=='NOT_EVALUATED' and row['identityBasis']=='RUNNER_ENVIRONMENT_NOT_INDEPENDENT_ATTESTATION','SAFE_STATUS_REJECTED')
 canonical=(json.dumps(row,sort_keys=True,separators=(',',':'))+'\n').encode()
 require(raw==canonical,'SAFE_STATUS_REJECTED')
 return canonical

def collect_statuses(root,ident):
 """Only validated fresh staging may be uploaded; prior status paths are untrusted."""
 root=Path(root).absolute();require(root.resolve()==root,'SAFE_PATH_REJECTED')
 src=root/TASK/'evidence/visual-candidate';dst=root/TASK/'artifacts/post-capture-screened-status'
 require(dst.parent.resolve()==dst.parent and not dst.exists() and not dst.is_symlink(),'SAFE_PATH_REJECTED')
 dst.mkdir(mode=0o700,parents=True)
 accepted=[];rejected=[]
 for index,name in enumerate(STATUS_TARGETS,1):
  try:
   raw=screened_status(regular(src/name,8192),name,ident)
   write_new(dst/name,raw)
   accepted.append({'file':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
  except BaseException as error:
   rejected.append({'item':'STATUS_'+str(index),'code':error_code(error)})
 report={'schemaVersion':1,'scope':'SCREENED_POST_CAPTURE_STATUS_COLLECTION_NOT_ACCEPTANCE',**ident,'status':'COLLECTED_SCREENED_STATUS_ONLY','files':accepted,'rejected':rejected,'acceptance':'NOT_EVALUATED'}
 write_new(dst/'status-collection-manifest.json',(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n').encode())
 return report

def collect_main():
 import sys
 require(sys.argv[1:]==['collect-statuses'],'CLI_ARGUMENTS')
 root=Path(os.environ['GITHUB_WORKSPACE']).absolute();report=collect_statuses(root,identity())
 output=Path(os.environ['GITHUB_OUTPUT']);require(output.resolve()==output.absolute(),'SAFE_PATH_REJECTED')
 with output.open('a') as stream:stream.write('safe_statuses=true\n')
 print(json.dumps({'status':'COLLECTED_SCREENED_STATUS_ONLY','accepted':len(report['files']),'rejected':len(report['rejected'])}))

if __name__=='__main__':
 try:collect_main()
 except BaseException as error:
  # Never invoke persist here: the untrusted raw status paths are not outputs.
  print(json.dumps({'status':'BLOCKED','code':error_code(error)}));raise SystemExit(3) from None
