#!/usr/bin/env python3
"""One fixed model-meta STRUCTURE projection. Never accepts inventory/source changes.
No raw strings, GUIDs or numerical payloads are exported. No native/project logs,
settings or other project inputs are opened. Run only after successful cleanup.
"""
import hashlib,json,math,os,re,stat,sys
from pathlib import Path
MAX_INPUT=65536;MAX_LINES=1024;MAX_LINE=1024;MAX_OUTPUT=131072;MAX_TOKENS=8192
TARGET='tasks/lottery-shop/unity/Assets/G3/Shop/Resources/G3/Shop/LotteryShop_Interior.fbx.meta'
SCOPE='FIXED_INTERIOR_META_STRUCTURE_ONLY_NOT_SOURCE_WAIVER_NOT_G3_PASS'
FIELDS=frozenset('fileFormatVersion guid ModelImporter serializedVersion internalIDToNameTable externalObjects first second type assembly name materials materialImportMode materialName materialSearch materialLocation animations legacyGenerateAnimations bakeSimulation resampleCurves optimizeGameObjects motionNodeName rigImportErrors rigImportWarnings animationImportErrors animationImportWarnings animationRetargetingWarnings animationDoRetargetingWarnings importAnimatedCustomProperties importConstraints animationCompression animationRotationError animationPositionError animationScaleError animationWrapMode extraExposedTransformPaths extraUserProperties clipAnimations isReadable importAnimation copyAvatar lastHumanDescriptionAvatarSource autoGenerateAvatarMappingWhenUnspecified meshes lODScreenPercentages globalScale meshCompression addColliders useSRGBMaterialColor sortHierarchyByName importVisibility importBlendShapes importCameras importLights fileIdsGeneration swapUVChannels generateSecondaryUV useFileUnits keepQuads weldVertices bakeAxisConversion preserveHierarchy skinWeights maxBonesPerVertex minBoneWeight meshOptimizationFlags indexFormat secondaryUVAngleDistortion secondaryUVAreaDistortion secondaryUVHardAngle secondaryUVMargin secondaryUVMinLightmapResolution secondaryUVMinObjectScale secondaryUVPackMargin secondaryUVPackMarginMethod secondaryUVPixelsPerUnit useFileScale strictVertexDataChecks tangentSpace normalSmoothAngle normalImportMode tangentImportMode normalCalculationMode legacyComputeAllNormalsFromSmoothingGroups blendShapeNormalImportMode normalSmoothingSource referencedClips importNormals importTangents importBlendShapeNormals animationType humanoidOversampling avatarSetup addHumanoidExtraRootOnlyWhenUsingAvatar importBlendShapeDeformPercent humanDescription human skeleton armTwist foreArmTwist upperLegTwist legTwist armStretch legStretch feetSpacing globalScale rootMotionBoneName hasTranslationDoF hasExtraRoot skeletonHasParents humanName boneName limit center axisLength min max x y z w r g b a position rotation scale defaultValues enforceIsOneObject scaleCompensation useT0AsRefPose sourceAvatar nameFileIdTable internalIDToNameTable internalID fileID userData assetBundleName assetBundleVariant importMaterials importPhysicalCameras importUnusedMaterial modelFileInfo uvMesh materialColor materialAlpha materialShininess materialSpecularColor'.split())
ATOMS=frozenset(('Material','UnityEngine.CoreModule','UnityEngine','true','false'))
PUNCT={'{':'MAP_OPEN','}':'MAP_CLOSE','[':'LIST_OPEN',']':'LIST_CLOSE',':':'COLON',',':'COMMA'}
KINDS=frozenset(('EMPTY','EMPTY_QUOTED','INTEGER','FLOAT','EXPONENT','NUMERIC_LIMIT','GUID','TEXT_REDACTED'))
TOKENS=KINDS|frozenset(PUNCT.values())|frozenset('FIELD:'+k for k in FIELDS)|frozenset('ENUM:'+k for k in ATOMS)
SENSITIVE={'userdata','assetbundlename','assetbundlevariant'}
SECRET=re.compile(r'password|passcode|secret|token|credential|license|privatekey|apikey',re.I)
NUMBER=re.compile(r'[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z')
class Rejected(ValueError):pass
def require(ok):
 if not ok:raise Rejected('INTERIOR_META_STRUCTURE_REJECTED')
def digest(b):return hashlib.sha256(b).hexdigest()
def stamp(s):return (s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
def read_fixed_path(path,maximum=MAX_INPUT):
 """Anchored O_NOFOLLOW for every component; no links, aliases or changed input."""
 p=Path(path);require(p.is_absolute() and str(p)==os.path.normpath(str(p)))
 fds=[os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)];anchors=[]
 try:
  for name in p.parts[1:-1]:
   old=os.stat(name,dir_fd=fds[-1],follow_symlinks=False);require(stat.S_ISDIR(old.st_mode))
   fd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fds[-1]);require((old.st_dev,old.st_ino)==(os.fstat(fd).st_dev,os.fstat(fd).st_ino));anchors.append((fds[-1],name,old.st_dev,old.st_ino));fds.append(fd)
  old=os.stat(p.name,dir_fd=fds[-1],follow_symlinks=False);require(stat.S_ISREG(old.st_mode) and old.st_nlink==1 and not(old.st_mode&0o111) and 0<old.st_size<=maximum)
  fd=os.open(p.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fds[-1]);fds.append(fd);require(stamp(os.fstat(fd))==stamp(old))
  raw=b''
  while True:
   b=os.read(fd,maximum+1-len(raw))
   if not b:break
   raw+=b;require(len(raw)<=maximum)
  require(stamp(os.fstat(fd))==stamp(old)==stamp(os.stat(p.name,dir_fd=fds[-2],follow_symlinks=False)))
  for parent,name,dev,ino in anchors:
   now=os.stat(name,dir_fd=parent,follow_symlinks=False);require(stat.S_ISDIR(now.st_mode) and (now.st_dev,now.st_ino)==(dev,ino))
  return raw
 finally:
  for fd in reversed(fds):os.close(fd)
def value_tokens(value):
 if value=='':return ['EMPTY']
 if value in ('""',"''"):return ['EMPTY_QUOTED']
 require(not any(c in value for c in '&*!|>'))
 out=[]
 for token in re.findall(r'[{}\[\]:,]|[^{}\[\]:,\s]+',value):
  if token in PUNCT:kind=PUNCT[token]
  elif re.fullmatch('[0-9a-f]{32}',token):kind='GUID'
  elif NUMBER.fullmatch(token):
   if len(token)>32 or not math.isfinite(float(token)) or abs(float(token))>2147483648:kind='NUMERIC_LIMIT'
   else:kind='EXPONENT' if 'e' in token.lower() else 'FLOAT' if '.' in token else 'INTEGER'
  elif token in FIELDS:kind='FIELD:'+token
  elif token in ATOMS:kind='ENUM:'+token
  else:kind='TEXT_REDACTED'
  out.append(kind);require(len(out)<=256)
 require(bool(out));return out
def project(raw,identity):
 require(0<len(raw)<=MAX_INPUT)
 try:text=raw.decode('ascii')
 except UnicodeError:raise Rejected('INTERIOR_META_STRUCTURE_REJECTED') from None
 require('\r' not in text and '\x00' not in text and all(c=='\n' or 32<=ord(c)<=126 for c in text))
 lines=text.splitlines();require(0<len(lines)<=MAX_LINES);rows=[];roots=set();owner=None;previous_depth=-1;previous_key=None;token_count=0
 for index,line in enumerate(lines,1):
  require(0<len(line)<=MAX_LINE)
  match=re.fullmatch(r'( *)(- )?([A-Za-z_][A-Za-z0-9_]*|[0-9]{1,19}): *(.*)',line);require(match is not None)
  spaces,dash,key,value=match.groups();indent=len(spaces);depth=indent+(2 if dash else 0);value=value.rstrip(' ')
  require(indent%2==0 and depth<=20 and not SECRET.search(key))
  # Scan every key-like token, including flow contents, before any output.
  for candidate in re.finditer(r"[\"']?\b([A-Za-z_][A-Za-z0-9_]*)[\"']? *:",line):
   nested_key=candidate[1];require(not SECRET.search(nested_key))
   if nested_key.lower() in SENSITIVE:require(candidate.start(1)==match.start(3))
  if key.lower() in SENSITIVE:require(key in {'userData','assetBundleName','assetBundleVariant'} and value in ('','""',"''"))
  if depth>previous_depth:require(previous_key is None or previous_key.lower() not in SENSITIVE)
  if indent==0:
   require(not dash and key in {'fileFormatVersion','guid','ModelImporter'} and key not in roots);roots.add(key);owner=key
   if key=='fileFormatVersion':require(value=='2')
   if key=='guid':require(re.fullmatch('[0-9a-f]{32}',value) is not None)
   if key=='ModelImporter':require(value=='')
  else:require(owner=='ModelImporter')
  tokens=value_tokens(value);token_count+=len(tokens);require(token_count<=MAX_TOKENS)
  rows.append(dict(line=index,indent=indent,dash=bool(dash),key=key if key in FIELDS else 'INTEGER_KEY' if key.isdigit() else 'UNKNOWN_KEY',tokens=tokens))
  previous_depth=depth;previous_key=key
 require(roots=={'fileFormatVersion','guid','ModelImporter'})
 result=dict(schemaVersion=1,scope=SCOPE,sourceCommit=identity['sourceCommit'],runId=identity['runId'],runAttempt=identity['runAttempt'],source='LotteryShop_Interior.fbx.meta',sourceSha256=digest(raw),sourceBytes=len(raw),sourceLines=len(lines),rows=rows,acceptance='NOT_EVALUATED',rawContentExported=False)
 return result
def screen(value):
 require(type(value)is dict and set(value)=={'schemaVersion','scope','sourceCommit','runId','runAttempt','source','sourceSha256','sourceBytes','sourceLines','rows','acceptance','rawContentExported'})
 require(value['schemaVersion']==1 and value['scope']==SCOPE and value['source']=='LotteryShop_Interior.fbx.meta' and value['acceptance']=='NOT_EVALUATED' and value['rawContentExported'] is False)
 require(type(value['sourceCommit'])is str and re.fullmatch('[0-9a-f]{40}',value['sourceCommit']) is not None)
 for key in ['runId','runAttempt']:require(type(value[key])is str and re.fullmatch('[1-9][0-9]{0,19}',value[key]) is not None)
 require(type(value['sourceSha256'])is str and re.fullmatch('[0-9a-f]{64}',value['sourceSha256']) is not None)
 require(type(value['sourceBytes'])is int and 0<value['sourceBytes']<=MAX_INPUT and type(value['sourceLines'])is int and 0<value['sourceLines']<=MAX_LINES)
 require(type(value['rows'])is list and len(value['rows'])==value['sourceLines']);total=0
 for i,row in enumerate(value['rows'],1):
  require(type(row)is dict and set(row)=={'line','indent','dash','key','tokens'} and type(row['line'])is int and row['line']==i and type(row['indent'])is int and 0<=row['indent']<=20 and row['indent']%2==0 and type(row['dash'])is bool)
  require(type(row['key'])is str and row['key'] in FIELDS|{'UNKNOWN_KEY','INTEGER_KEY'})
  require(type(row['tokens'])is list and 0<len(row['tokens'])<=256 and all(type(t)is str and t in TOKENS for t in row['tokens']));total+=len(row['tokens'])
 require(total<=MAX_TOKENS);return value
def encode(value):
 screen(value);raw=(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode();require(len(raw)<=MAX_OUTPUT);return raw
def output_dir(temp,run,attempt):
 p=Path(temp);require(p.is_absolute() and str(p)==os.path.normpath(str(p)) and p.absolute()==p.resolve())
 for parent in [p,*p.parents]:require(stat.S_ISDIR(parent.lstat().st_mode))
 target=p/('lottery-interior-meta-structure-'+run+'-'+attempt);os.mkdir(target,0o700);require(target.absolute()==target.resolve() and stat.S_ISDIR(target.lstat().st_mode));return target
def export():
 e=os.environ;require(e.get('GITHUB_REPOSITORY')=='yangerstar1/task-workbench' and e.get('META_GUARD_OUTCOME')=='success' and e.get('META_FINISH_OUTCOME')=='success' and e.get('META_CAPTURE_OUTCOME') in {'success','failure'})
 ident=dict(sourceCommit=e.get('GITHUB_SHA',''),runId=e.get('GITHUB_RUN_ID',''),runAttempt=e.get('GITHUB_RUN_ATTEMPT',''))
 require(re.fullmatch('[0-9a-f]{40}',ident['sourceCommit']) is not None and all(re.fullmatch('[1-9][0-9]{0,19}',ident[k]) is not None for k in ['runId','runAttempt']))
 root=Path(e['GITHUB_WORKSPACE']);require(root.is_absolute() and root.absolute()==root.resolve())
 # Only this one project input is opened. No glob, logs, settings or source receipt.
 raw=read_fixed_path(root/TARGET);result=project(raw,ident);projected=encode(result)
 # Independently screen a fresh decode before creating the upload file.
 require(encode(json.loads(projected))==projected)
 destination=output_dir(e['RUNNER_TEMP'],ident['runId'],ident['runAttempt'])/'interior-meta-structure.json'
 fd=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as stream:stream.write(projected);stream.flush();os.fsync(stream.fileno())
 info=destination.lstat();require(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_size==len(projected))
 require(read_fixed_path(destination,MAX_OUTPUT)==projected)
 print('INTERIOR_META_STRUCTURE_EXPORTED_NOT_SOURCE_WAIVER')
def self_test():
 import tempfile,unittest
 class Tests(unittest.TestCase):
  ident=dict(sourceCommit='a'*40,runId='123',runAttempt='1')
  prefix=b'fileFormatVersion: 2\nguid: '+b'a'*32+b'\nModelImporter:\n'
  def test_redaction_and_numeric_shapes(self):
   raw=self.prefix+b'  unknownField: {unknownKey: PRIVATE_SENTINEL, x: 12, y: 0.1, z: 2e-3}\n  userData: \n';r=project(raw,self.ident);b=encode(r);self.assertNotIn(b'PRIVATE_SENTINEL',b);self.assertNotIn(b'unknownField',b);self.assertNotIn(b'unknownKey',b);self.assertEqual(r['rows'][3]['tokens'],['MAP_OPEN','TEXT_REDACTED','COLON','TEXT_REDACTED','COMMA','FIELD:x','COLON','INTEGER','COMMA','FIELD:y','COLON','FLOAT','COMMA','FIELD:z','COLON','EXPONENT','MAP_CLOSE'])
  def test_sensitive_scan_including_late_lines(self):
   for tail in [b'  userData: PRIVATE_SENTINEL\n',b'  assetBundleName: name\n',b'  assetBundleVariant: value\n',b'  APIKey: value\n',b'  userData:\n    child: value\n',b'  ordinary: {userData: PRIVATE_SENTINEL}\n',b'  ordinary: {apiKey: PRIVATE_SENTINEL}\n',b'  ordinary: {"userData": PRIVATE_SENTINEL}\n',b'  ordinary: {"apiKey": PRIVATE_SENTINEL}\n']:
    with self.subTest(tail=tail[:15]):self.assertRaises(Rejected,project,self.prefix+b'  unknownField: {q: thing}\n'+tail,self.ident)
  def test_encoding_size_and_root_rejection(self):
   for raw in [self.prefix+b'  x: &alias\n',self.prefix+b'  x: \xff\n',self.prefix.replace(b'\n',b'\r\n'),self.prefix+b'  x: '+b'a'*MAX_LINE+b'\n',b'x'*65537,self.prefix.replace(b'ModelImporter',b'OtherImporter')]:self.assertRaises(Rejected,project,raw,self.ident)
  def test_projection_rejects_injected_strings(self):
   for key in ['key','tokens']:
    r=project(self.prefix+b'  x: 1\n',self.ident);r['rows'][-1][key]='PRIVATE_SENTINEL' if key=='key' else ['PRIVATE_SENTINEL'];self.assertRaises(Rejected,encode,r)
  def test_nofollow_alias_and_stale_output(self):
   with tempfile.TemporaryDirectory() as t:
    p=Path(t);f=p/'model.meta';f.write_bytes(self.prefix);self.assertEqual(read_fixed_path(f),self.prefix);(p/'link').symlink_to(f);self.assertRaises((Rejected,OSError),read_fixed_path,p/'link');os.link(f,p/'hard');self.assertRaises(Rejected,read_fixed_path,f);output_dir(t,'123','1');self.assertRaises(FileExistsError,output_dir,t,'123','1')
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests));return 0 if result.wasSuccessful() else 1
if __name__=='__main__':
 if sys.argv[1:]==['--self-test']:raise SystemExit(self_test())
 try:require(len(sys.argv)==1);export()
 except Exception:print('INTERIOR_META_STRUCTURE_REJECTED');raise SystemExit(1)
