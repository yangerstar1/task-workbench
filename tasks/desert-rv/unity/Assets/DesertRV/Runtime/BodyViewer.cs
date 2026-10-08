using System.Collections.Generic;
using System.Collections;
using System.Runtime.InteropServices;
using UnityEngine;
namespace DesertRV {
public class BodyViewer : MonoBehaviour {
#if UNITY_WEBGL && !UNITY_EDITOR
    [DllImport("__Internal")] static extern void DesertRVReviewReady();
#endif
    IEnumerator Start(){yield return new WaitForEndOfFrame();
#if UNITY_WEBGL && !UNITY_EDITOR
        DesertRVReviewReady();
#endif
    }
    public Transform body;
    public Camera view;
    public Texture2D checker;
    public Transform garageBench;
    public GameObject ramModule,arcModule,roofCargo;
    public void ReviewModule(string key){
        if(ramModule)ramModule.SetActive(key=="ram"||key=="both");
        if(arcModule)arcModule.SetActive(key=="arc"||key=="both");
        if(roofCargo)roofCargo.SetActive(key!="arc"&&key!="both");
    }
    enum Mode { Orbit,Driving,Walking }
    Mode mode;
    float yaw=145,pitch=19,distance=10,speed,verticalVelocity,doorAngle;
    float frameWindow,shownFps;int frameCount;
    bool paused,doorOpen,checking,showPanel=true,inspectionLook;
    Transform hinge,step;
    CharacterController walker;
    Quaternion closedDoor;
    Vector3 hingeAxis,forwardLocal;
    Vector3 Forward=>body.TransformDirection(forwardLocal).normalized;
    float heading=>Quaternion.LookRotation(Forward).eulerAngles.y;
    readonly Dictionary<Material,Texture> originalMaps=new Dictionary<Material,Texture>();
    void Awake(){
        foreach(var t in body.GetComponentsInChildren<Transform>()){
            if(t.name=="RIG-entry_door_pivot")hinge=t;
            if(t.name=="GEO-entry_step")step=t;
            if(t.name=="GEO-windscreen"){
                var forward=t.GetComponent<Renderer>().bounds.center-body.position;forward.y=0;
                forwardLocal=body.InverseTransformDirection(forward.normalized);
            }
        }
        closedDoor=hinge.localRotation;hingeAxis=hinge.InverseTransformDirection(Vector3.up);
        var player=new GameObject("Inspection walker");walker=player.AddComponent<CharacterController>();
        // The first tread is about 0.367 m above this road surface, including
        // the vehicle offset. A 0.33 m limit could block entry at small timesteps.
        walker.height=1.62f;walker.radius=.19f;walker.center=new Vector3(0,.81f,0);walker.stepOffset=.38f;walker.skinWidth=.025f;walker.enabled=false;
        view.nearClipPlane=.045f;
        foreach(var r in body.GetComponentsInChildren<Renderer>())
            if(r.name=="GEO-coach_body_shell"||r.name=="GEO-entry_door")foreach(var m in r.materials)originalMaps[m]=m.mainTexture;
    }
    void Update(){
        frameWindow+=Time.unscaledDeltaTime;frameCount++;
        if(frameWindow>=1){shownFps=frameCount/frameWindow;frameWindow=0;frameCount=0;}
        if(Input.GetKeyDown(KeyCode.Escape)){paused=true;Cursor.lockState=CursorLockMode.None;Cursor.visible=true;}
        if(Input.GetKeyDown(KeyCode.H))showPanel=!showPanel;
        if(paused)return;
        if(Input.GetKeyDown(KeyCode.C))ToggleChecker();
        if(Input.GetKeyDown(KeyCode.G)&&garageBench)WalkGarage();
        doorAngle=Mathf.MoveTowards(doorAngle,doorOpen?-100:0,Time.deltaTime*155);
        hinge.localRotation=closedDoor*Quaternion.AngleAxis(doorAngle,hingeAxis);
        if(mode==Mode.Orbit){
            yaw+=Input.GetAxisRaw("Horizontal")*Time.deltaTime*50;
            pitch=Mathf.Clamp(pitch+Input.GetAxisRaw("Vertical")*Time.deltaTime*30,4,78);
            distance=Mathf.Clamp(distance-Input.mouseScrollDelta.y*.5f,4,40);
        }else if(mode==Mode.Driving){
            float target=Input.GetAxisRaw("Vertical")*7;
            speed=Mathf.MoveTowards(speed,target,Time.deltaTime*(target==0?8:4));
            body.Rotate(0,Input.GetAxisRaw("Horizontal")*speed*9*Time.deltaTime,0,Space.World);
            body.position+=Forward*speed*Time.deltaTime;
            if(body.position.magnitude>13)body.position=body.position.normalized*13;
            if(Input.GetKeyDown(KeyCode.E))Walk(false);
        }else{
            var pointer=Input.mousePosition;
            if(!inspectionLook&&Input.GetMouseButtonDown(0)&&Cursor.lockState!=CursorLockMode.Locked&&pointer.x>=0&&pointer.x<Screen.width&&pointer.y>=0&&pointer.y<Screen.height&&(!showPanel||pointer.y<Screen.height-185))Cursor.lockState=CursorLockMode.Locked;
            if(!inspectionLook&&Cursor.lockState==CursorLockMode.Locked){yaw+=Input.GetAxis("Mouse X")*1.8f;pitch=Mathf.Clamp(pitch-Input.GetAxis("Mouse Y")*1.8f,-70,70);}
            if(Input.GetKey(KeyCode.LeftArrow))yaw-=60*Time.deltaTime;
            if(Input.GetKey(KeyCode.RightArrow))yaw+=60*Time.deltaTime;
            if(Input.GetKey(KeyCode.UpArrow))pitch-=40*Time.deltaTime;
            if(Input.GetKey(KeyCode.DownArrow))pitch+=40*Time.deltaTime;
            Vector3 input=new Vector3((Input.GetKey(KeyCode.D)?1:0)-(Input.GetKey(KeyCode.A)?1:0),0,(Input.GetKey(KeyCode.W)?1:0)-(Input.GetKey(KeyCode.S)?1:0));
            input=Quaternion.Euler(0,yaw,0)*Vector3.ClampMagnitude(input,1)*1.8f;
            verticalVelocity=walker.isGrounded?-1:verticalVelocity-16*Time.deltaTime;
            walker.Move((input+Vector3.up*verticalVelocity)*Time.deltaTime);
            if(Input.GetKeyDown(KeyCode.E)&&Vector3.Distance(walker.transform.position,hinge.position)<2.6f)doorOpen=!doorOpen;
            if(Input.GetKeyDown(KeyCode.F)&&Vector3.Distance(walker.transform.position,body.position)<4)Drive();
        }
        Physics.SyncTransforms();
    }
    void LateUpdate(){
        if(mode==Mode.Walking){view.fieldOfView=66;view.transform.SetPositionAndRotation(walker.transform.position+Vector3.up*1.52f,Quaternion.Euler(pitch,yaw,0));return;}
        view.fieldOfView=44;
        Vector3 centre=body.position+Vector3.up*1.3f;
        if(mode==Mode.Driving)centre+=Forward*2.2f;
        if(mode==Mode.Orbit&&distance>20&&garageBench){var to=garageBench.GetComponent<Renderer>().bounds.center-body.position;to.y=0;centre+=to*.44f;}
        var rotation=mode==Mode.Driving?Quaternion.Euler(74,heading,0):Quaternion.Euler(pitch,yaw,0);
        view.transform.position=centre+rotation*new Vector3(0,0,mode==Mode.Driving?-26:-distance);view.transform.LookAt(centre);
    }
    void Orbit(float y,float p){mode=Mode.Orbit;walker.enabled=false;speed=0;yaw=y;pitch=p;distance=10;Cursor.lockState=CursorLockMode.None;Cursor.visible=true;}
    void Drive(){mode=Mode.Driving;walker.enabled=false;speed=0;doorOpen=false;Cursor.lockState=CursorLockMode.None;Cursor.visible=true;}
    void Walk(bool inside,bool lockPointer=true){
        mode=Mode.Walking;speed=0;doorOpen=true;walker.enabled=false;
        inspectionLook=!lockPointer;
        var entry=step.GetComponent<Renderer>().bounds.center;
        var right=Vector3.Cross(Vector3.up,Forward);
        var outward=right*Mathf.Sign(Vector3.Dot(entry-body.position,right));
        var position=inside?body.position+Forward*.55f+Vector3.up*.86f:entry+outward*.90f;
        if(!inside)position.y=.04f;
        walker.transform.position=position;walker.enabled=true;verticalVelocity=0;
        var facing=inside?-Forward:-outward;yaw=Quaternion.LookRotation(facing).eulerAngles.y;pitch=inside?8:0;
        Cursor.lockState=lockPointer?CursorLockMode.Locked:CursorLockMode.None;Cursor.visible=!lockPointer;
    }
    void ToggleChecker(){checking=!checking;foreach(var pair in originalMaps)pair.Key.mainTexture=checking?checker:pair.Value;}
    public void PointerLockUnavailable(){Cursor.lockState=CursorLockMode.None;Cursor.visible=true;}
    public void ReviewView(string key){
        paused=false;showPanel=false;
        if(key=="top"){Orbit(-125,58);distance=34;}
        else if(key=="garage")WalkGarage(false);
        else if(key=="inside")Walk(true,false);
        else if(key=="drive")Drive();
        else Orbit(145,19);
    }
    void WalkGarage(bool lockPointer=true){
        Walk(false,lockPointer);walker.enabled=false;
        var bench=garageBench.GetComponent<Renderer>().bounds.center;var toward=body.position-bench;toward.y=0;
        var point=bench-toward.normalized*1.00f+Vector3.Cross(Vector3.up,toward.normalized)*.90f;point.y=.06f;walker.transform.position=point;walker.enabled=true;
        var look=body.position-point;look.y=0;yaw=Quaternion.LookRotation(look).eulerAngles.y;pitch=8;
    }
    void OnApplicationFocus(bool focus){if(!focus){paused=true;Cursor.lockState=CursorLockMode.None;Cursor.visible=true;}}
    void OnGUI(){
        GUI.skin.label.fontSize=20;GUI.skin.button.fontSize=20;
        if(showPanel){
        GUI.Box(new Rect(15,15,1020,165),"");
        GUI.Label(new Rect(28,24,990,32),"RV CANDIDATE | "+mode+" | "+shownFps.ToString("F0")+" FPS | G: garage | H: panel");
        GUI.Label(new Rect(28,58,990,30),mode==Mode.Walking?"WASD walk | mouse / arrows look | E door | F drive | ESC pause":"WASD orbit / drive | scroll zoom | E leave parked RV | C UV checker");
        if(GUI.Button(new Rect(28,96,120,32),"FRONT"))Orbit(145,19);
        if(GUI.Button(new Rect(158,96,120,32),"REAR"))Orbit(-35,19);
        if(GUI.Button(new Rect(288,96,120,32),"TOP")){Orbit(-125,58);distance=garageBench?34:10;}
        if(GUI.Button(new Rect(418,96,120,32),"SIDE"))Orbit(90,10);
        if(GUI.Button(new Rect(548,96,140,32),"INSIDE"))Walk(true);
        if(GUI.Button(new Rect(698,96,140,32),"OUTSIDE"))Walk(false);
        if(GUI.Button(new Rect(848,96,160,32),"DRIVE"))Drive();
        if(mode==Mode.Walking)GUI.Label(new Rect(28,139,990,32),"Feet "+walker.transform.position.ToString("F2")+" | Mouse "+Cursor.lockState);
        }
        if(paused&&GUI.Button(new Rect(Screen.width/2-140,Screen.height/2-25,280,50),"RESUME INSPECTION")){paused=false;if(mode==Mode.Walking){Cursor.lockState=CursorLockMode.Locked;Cursor.visible=false;}}
    }
}}
