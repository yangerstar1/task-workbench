using System;
using System.IO;
using UnityEngine;

namespace DesertRV.Editor {
public static class StormChecks {
    static int checks;
    static void Expect(bool ok,string why){checks++;if(!ok)throw new Exception(why);}
    static bool Near(double a,double b)=>Math.Abs(a-b)<1e-7;
    static SessionState Session(double start=-40,double speed=2,double dps=4){
        var s=new SessionState();
        if(!s.ConfigureStorm(start,speed,dps))throw new Exception("Fixture storm configuration failed");
        s.Start();return s;
    }
    static void FinishStage(SessionState s,ComponentPart part,string id){
        if(!s.TryCollect(id,part)||!s.TryInstall(part))throw new Exception("Fixture could not install component");
        s.SetObjectivesResolved(true);
        if(!s.TryAdvance())throw new Exception("Fixture could not advance stage");
        s.CompleteLoading();
    }
    public static void Run(){
        checks=0;
        var fast=Session();var greedy=Session();
        fast.AdvanceStorm(10,1000,1000);greedy.AdvanceStorm(17,1000,1000);
        FinishStage(fast,ComponentPart.RamPart,"ram");FinishStage(greedy,ComponentPart.RamPart,"ram");
        Expect(Near(fast.StormFrontProgress,-20)&&Near(greedy.StormFrontProgress,-6),"Stage transition reset global storm progress");
        Expect(Near(greedy.StormFrontProgress-fast.StormFrontProgress,7*2),"Extra looting must carry its full fixed-speed cost to the next stage");
        Expect(!greedy.ConfigureStorm(-999,1,1)&&Near(greedy.StormSpeed,2),"Storm speed changed after the journey started");
        greedy.AdvanceStorm(3,1000,1000);FinishStage(greedy,ComponentPart.Coil,"coil");
        Expect(greedy.SceneId==3&&Near(greedy.StormFrontProgress,0)&&Near(greedy.StormElapsedSeconds,20),"Storm restarted at region three");
        var dead=Session();dead.AdvanceStorm(17,1000,1000);FinishStage(dead,ComponentPart.RamPart,"ram");
        dead.AdvanceStorm(12,1000,1000);dead.DamagePlayer(100);dead.RestartJourney();
        Expect(dead.SceneId==1&&dead.Upgrades==VehicleUpgrades.None&&Near(dead.StormFrontProgress,-40),"Failure must reset the entire journey, not restore a checkpoint");
        FinishStage(dead,ComponentPart.RamPart,"ram");FinishStage(dead,ComponentPart.Coil,"coil");
        dead.AdvanceStorm(2,1000,1000);dead.DamageVehicle(300);dead.RestartJourney();
        Expect(dead.SceneId==1&&Near(dead.StormFrontProgress,-40)&&dead.Upgrades==VehicleUpgrades.None,"Vehicle failure must also clear the whole journey");

        var driving=Session(0);var walking=Session(0);walking.SetControl(ControlMode.OnFoot);
        driving.AdvanceStorm(2.5,-10,-10);walking.AdvanceStorm(2.5,-10,-10);
        Expect(driving.PlayerHealth==90&&walking.PlayerHealth==90,"Driving/being in RV incorrectly shelters player from storm damage");
        Expect(driving.VehicleHealth==300&&walking.VehicleHealth==300,"Storm must never damage the RV");
        var front=driving.StormFrontProgress;driving.Pause();driving.AdvanceStorm(100,-10,-10);
        Expect(Near(front,driving.StormFrontProgress)&&driving.PlayerHealth==90,"Pause advanced storm or applied damage");
        driving.Resume();driving.AdvanceStorm(1,-10,-10);
        Expect(Near(driving.StormFrontProgress,front+2)&&driving.PlayerHealth==86,"Resume changed speed or damage rate");

        var single=Session(0,2,12);var split=Session(0,2,12);
        single.AdvanceStorm(2,10,-10);split.AdvanceStorm(1,10,0);split.AdvanceStorm(1,0,-10);
        Expect(single.PlayerHealth==86&&split.PlayerHealth==86,"Damage differs when entering the range with different frame sizes");
        var exiting=Session(0,2,12);exiting.AdvanceStorm(2,-10,10);
        Expect(exiting.PlayerHealth==85,"Leaving storm applied a full frame of damage");
        exiting.AdvanceStorm(5,10,1000);
        Expect(exiting.PlayerHealth==85&&!exiting.IsInStorm(1000),"Damage continued outside storm range");
        var manyFrames=Session(0,2,7);var fewFrames=Session(0,2,7);
        for(int i=0;i<180;i++)manyFrames.AdvanceStorm(1.0/60,-10,-10);
        fewFrames.AdvanceStorm(3,-10,-10);
        Expect(manyFrames.PlayerHealth==79&&fewFrames.PlayerHealth==79&&Near(manyFrames.StormFrontProgress,fewFrames.StormFrontProgress),"Fractional damage or progression depends on frame rate");

        var failed=Session(0,2,100);failed.AdvanceStorm(1,-10,-10);front=failed.StormFrontProgress;
        failed.AdvanceStorm(10,-10,-10);
        Expect(failed.Status==SessionStatus.Failed&&Near(front,failed.StormFrontProgress),"Failed session kept advancing the storm");
        failed.RestartJourney();Expect(failed.PlayerHealth==100&&Near(failed.StormFrontProgress,0),"Fresh journey did not reset initial storm");
        var fresh=Session();Expect(Near(fresh.StormFrontProgress,-40)&&Near(fresh.StormElapsedSeconds,0),"Starting over kept earlier run's storm debt");
        greedy.SetObjectivesResolved(true);greedy.SetGateOpen(true);greedy.TryReachSafety(true);front=greedy.StormFrontProgress;greedy.AdvanceStorm(20,-100,-100);
        Expect(greedy.Status==SessionStatus.Completed&&Near(greedy.StormFrontProgress,front),"Completed journey kept applying storm simulation");

        SessionChecks.Run();
        var report="DESERT_RV_STORM_CHECKS_PASSED: "+checks+"\nExisting SessionChecks also passed.\nScope: pure session logic; actual range rendering, world mapping, Unity gameplay and Android remain unverified.\n";
        var path=Path.GetFullPath(Path.Combine(Application.dataPath,"../../output/unity/storm-checks.txt"));
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllText(path,report);
        Debug.Log(report);
    }
}
}
