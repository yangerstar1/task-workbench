"""Write the finite candidate output contract. Native authoring asserts exact membership."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[2]
common={'Ground':['Sand'],'Road':['Asphalt'],'Shoulder':['Sand'],'ReliefWest':['Sand'],'ReliefEast':['Sand'],'GroundWear':['Oil'],'PullOff':['TrackSand']}
regions={
1:{'Forecourt':['Concrete'],'ForecourtDust':['Sand'],'ForecourtWear':['Oil'],'PumpDetails':['Ochre','Steel'],'StationRoof':['Ivory','Steel','Rubber'],'CanopyUpper':['Oxide','Ivory','Steel','Lamp'],'ForecourtDrain':['Steel'],'StationServiceBase':['Concrete'],'StationFuel':['Ivory','Steel','Concrete','Oxide'],'StationBack':['Steel','Concrete','Oxide','Ivory'],'StationWallLeft':['Plaster'],'StationWallRight':['Plaster'],'StationWallRear':['Plaster'],'StationRoofBase':['Concrete'],'CanopyBase':['Concrete'],'StationFascia':['Oxide']},
2:{'Container0':['Sheet'],'Container1':['Sheet'],'Container2':['Sheet'],'YardGroundWest':['Concrete'],'YardGroundEast':['Concrete'],'ScrapStacks':['Oxide','Steel'],'YardWorkshop':['Sheet','Steel','Lamp'],'YardPipeStore':['Steel','Oxide'],'YardRearWest':['Steel','Concrete','Oxide'],'YardRearEast':['Steel','Concrete','Ivory']},
3:{'BeaconGroundWest':['Concrete'],'BeaconGroundEast':['Concrete'],'RelayHouse':['Steel','Concrete','Ivory'],'RelayCanopy':['Sheet','Steel','Lamp'],'RelayBatteries':['Ivory','Steel'],'TowerUpper':['Steel','Ivory'],'TowerLadder':['Steel','Ivory'],'TowerFixtures':['Steel','Lamp']}}
materials=['Sand','TrackSand','Sheet','Asphalt','Concrete','Plaster','Oxide','Steel','Ivory','Ochre','Rubber','Oil','Lamp','Factory']
folder='Assets/DesertRV/Scenes/Journey/EnvironmentV4'
keys={r:sorted(f'{g}-{m}' for g,ms in {**common,**groups}.items() for m in ms) for r,groups in regions.items()}
files=[f'{folder}/Surface-{m}.mat' for m in materials]+[f'{folder}/R{r}-{key}.asset' for r,items in keys.items() for key in items]
contract={'schema':1,'status':'planned-exact-output-membership-native-author-must-verify','base_public_commit':'8b45b3c40e0752eed65ede5f3136a50761bd1a38','generated_folder':folder,'region_mesh_keys':keys,'material_names':materials,'files':sorted(files),'metadata_files':sorted([f+'.meta' for f in files]+[folder+'.meta']),'required_source_prefix':'Assets/DesertRV/Art/EnvironmentV4/','optional_or_omitted_files':[],'note':'Register each exact file and meta in new producer export contract. Do not allow wildcard. Materials are shared. Old producer restore bytes cannot be reused.'}
(ROOT/'art/environment-v4/generated-contract.json').write_text(json.dumps(contract,indent=2)+'\n')
p=ROOT/'unity/Assets/DesertRV/Editor/JourneySceneAuthoring.EnvironmentPolish.cs';s=p.read_text()
start=s.index('        // ENVIRONMENT_V4_CONTRACT_BEGIN') if '        // ENVIRONMENT_V4_CONTRACT_BEGIN' in s else s.index('        static void AuthorEnvironmentPolish')
end=s.index('        // ENVIRONMENT_V4_CONTRACT_END',start)+len('        // ENVIRONMENT_V4_CONTRACT_END\n') if '        // ENVIRONMENT_V4_CONTRACT_END' in s else start
method='        // ENVIRONMENT_V4_CONTRACT_BEGIN\n        static string[] PolishExpectedMeshNames(int region)\n        {\n            switch(region)\n            {\n'
for r,items in keys.items():method+='                case '+str(r)+': return new[]{'+','.join('"'+i+'"' for i in items)+'};\n'
method+='                default: throw new ArgumentOutOfRangeException(nameof(region));\n            }\n        }\n        // ENVIRONMENT_V4_CONTRACT_END\n'
p.write_text(s[:start]+method+s[end:])
print('Meshes', {r:len(i) for r,i in keys.items()},'Materials',len(materials),'Payload files',len(files))
