using UnityEngine;

namespace Lottery.G3.Interaction
{
    // Small single-room body. Collision prevents walking through the table/counter.
    public sealed class G3ShopWalk : MonoBehaviour
    {
        CharacterController body;Camera camera;float yaw,pitch=8;bool initialized;
        public Vector3 SavedPosition=>transform.position;
        public Quaternion SavedRotation=>Quaternion.Euler(pitch,yaw,0);
        public void Initialize(Camera sceneCamera)
        {
            camera=sceneCamera;transform.position=new Vector3(0,0,-1.65f);body=gameObject.AddComponent<CharacterController>();
            body.height=1.72f;body.radius=.18f;body.center=new Vector3(0,.86f,0);body.stepOffset=.15f;body.skinWidth=.025f;initialized=true;
        }
        public void Move(Vector2 local,float turn,float delta)
        {
            if(!initialized)return;yaw+=turn*75*delta;
            Vector3 direction=Quaternion.Euler(0,yaw,0)*new Vector3(local.x,0,local.y);if(direction.sqrMagnitude>1)direction.Normalize();
            body.Move((direction*1.15f+Vector3.down*2)*delta);ApplyCamera();
        }
        public void Look(Vector2 pixels)
        {yaw+=pixels.x*.13f;pitch=Mathf.Clamp(pitch-pixels.y*.10f,-30,45);ApplyCamera();}
        public void ApplyCamera(){if(camera!=null){camera.transform.position=transform.position+new Vector3(0,1.58f,0);camera.transform.rotation=Quaternion.Euler(pitch,yaw,0);}}
    }
    public sealed class G3WorldTarget : MonoBehaviour {public G3Panel Panel;public bool IsTable;}
}
