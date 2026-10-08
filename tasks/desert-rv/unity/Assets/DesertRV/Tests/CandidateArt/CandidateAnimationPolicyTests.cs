using System;
using System.Reflection;
using NUnit.Framework;
namespace DesertRV.Tests
{
    public sealed class CandidateAnimationPolicyTests
    {
        static bool Call(string method,params object[] args)=> (bool)Type.GetType("DesertRV.Editor.JourneyCandidateArtImport, Assembly-CSharp-Editor",true).GetMethod(method,BindingFlags.Static|BindingFlags.NonPublic).Invoke(null,args);
        [Test] public void OnlyArmoredAttackGetsTheSourceLoopException()
        {
            Assert.That(Call("AllowedLoop","armored","Attack"),Is.True);
            foreach(string kind in new[]{"pouncer","weapon"})Assert.That(Call("AllowedLoop",kind,"Attack"),Is.False);
            foreach(string state in new[]{"Windup","Recover","Hit","Death","Fire","Reload"})Assert.That(Call("AllowedLoop","armored",state),Is.False);
            Assert.That(Call("AllowedLoop","weapon","Idle"),Is.True);Assert.That(Call("AllowedLoop","pouncer","Walk"),Is.True);
        }
        [Test] public void EqualKeyValuesDoNotExcuseUnsafeTangents()
        {
            foreach(float t in new[]{float.NaN,.000001f,-.000001f,1f,-1f})Assert.That(Call("SafeConstantTangent",t),Is.False);
            foreach(float t in new[]{0f,float.PositiveInfinity,float.NegativeInfinity})Assert.That(Call("SafeConstantTangent",t),Is.True);
        }
    }
}
