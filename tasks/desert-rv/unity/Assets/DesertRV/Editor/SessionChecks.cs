using System;
using UnityEngine;
namespace DesertRV.Editor {
    public static class SessionChecks {
        static int checks;
        static void Expect(bool condition,string message){checks++;if(!condition)throw new Exception(message);}
        public static void Run(){
            checks=0;var s=new SessionState();s.ConfigureStorm(-40,2,7);s.Start();
            Expect(s.TryCollect("station-ram",ComponentPart.RamPart),"First pickup must work");
            Expect(!s.TryCollect("station-ram",ComponentPart.RamPart),"Duplicate pickup must not settle twice");
            Expect(s.TryInstall(ComponentPart.RamPart)&&!s.HasPart(ComponentPart.RamPart),"Install consumes its component");
            Expect(!s.TryInstall(ComponentPart.RamPart),"Duplicate installation must fail");
            s.DamagePlayer(100);s.RestartJourney();
            Expect(s.SceneId==1&&s.Upgrades==VehicleUpgrades.None,"Death clears all journey upgrades");
            Expect(s.TryCollect("station-ram",ComponentPart.RamPart),"Retry rebuilds pickup availability");
            s.TryInstall(ComponentPart.RamPart);s.DamagePlayer(9);s.DamageVehicle(40);s.TryFire();s.TryRepair();s.SetObjectivesResolved(true);Expect(s.TryAdvance()&&s.SceneId==2,"Advance to region 2");s.CompleteLoading();
            Expect(s.PlayerHealth==91&&s.VehicleHealth==300&&s.LoadedAmmo==11&&s.RepairKits==1,"Region transition must preserve real supplies and health");
            Expect(!s.RestartJourney(),"Cannot reset a living journey for free supplies");
            s.TryCollect("salvage-coil",ComponentPart.Coil);s.TryInstall(ComponentPart.Coil);s.SetGateOpen(true);s.SetPowerConnected(true);
            s.DamageVehicle(300);s.RestartJourney();
            Expect(s.SceneId==1&&s.Upgrades==VehicleUpgrades.None&&!s.GateOpen&&!s.PowerConnected,"Failure resets the entire journey and clears power/gate");
            Expect(s.VehicleHealth==300&&s.LoadedAmmo==12,"New journey starts with clean supplies");
            s.Pause();s.DamagePlayer(100);Expect(s.PlayerHealth==100&&!s.TryFire(),"Paused simulation cannot consume health or ammunition");
            s.Resume();for(int i=0;i<20;i++)s.TryFire();Expect(s.LoadedAmmo==0,"Magazine cannot become negative");
            s.Reload();Expect(s.LoadedAmmo==12&&s.ReserveAmmo==84,"Reload transfers exactly the required ammo");
            var fresh=new SessionState();Expect(fresh.SceneId==1&&fresh.Upgrades==VehicleUpgrades.None,"New state starts a fresh journey");
            Debug.Log("DESERT_RV_SESSION_CHECKS_PASSED: "+checks);
        }
    }
}
