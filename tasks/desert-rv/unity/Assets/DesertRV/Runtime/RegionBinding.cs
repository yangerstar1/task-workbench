using System;
using System.Collections.Generic;
using UnityEngine;

namespace DesertRV
{
    [Serializable] public sealed class RegionWave { public BeastActor[] enemies; }

    // Environment-only binding. The RV, camera and bench belong to the persistent root.
    public sealed class RegionBinding : MonoBehaviour
    {
        [Range(1, 3)] public int region = 1;
        public Transform spawn, exit, salvage, powerPoint;
        public Collider exitVolume, safeZone, salvageSurface, powerSurface, ramGate;
        public GameObject salvageVisual;
        public BeastActor[] guards, roadBeasts;
        public RegionWave[] waves;
        public Vector3 progressDirection = Vector3.forward;
        public double regionOffset;
        public float chargeSeconds = 30;
        public bool combatAssetsVerified, environmentVerified;
        public string pickupId;
        public double WorldProgress(Vector3 position) => regionOffset + Vector3.Dot(position - spawn.position, progressDirection.normalized);
        public static bool Contains(Collider volume, Vector3 point) => volume && volume.enabled &&
            volume.gameObject.activeInHierarchy && (volume.ClosestPoint(point) - point).sqrMagnitude < .0001f;
        public bool VehicleInsideExit(JourneyMotor motor) => Contains(exitVolume, motor.vehicle.position);
        public bool VehicleInsideSafety(JourneyMotor motor) => Contains(safeZone, motor.vehicle.position);
        public IEnumerable<BeastActor> AllEnemies()
        {
            if (guards != null) foreach (var e in guards) if (e) yield return e;
            if (roadBeasts != null) foreach (var e in roadBeasts) if (e) yield return e;
            if (waves != null) foreach (var wave in waves) if (wave != null && wave.enemies != null)
                foreach (var e in wave.enemies) if (e) yield return e;
        }
        public bool Validate(out string reason)
        {
            reason = null;
            if (!environmentVerified || !combatAssetsVerified) reason = "地区场景或战斗资产尚未验收。";
            else if (region < 1 || region > 3 || !spawn || !exitVolume || progressDirection.sqrMagnitude < .99f || float.IsNaN(progressDirection.sqrMagnitude) || float.IsInfinity(progressDirection.sqrMagnitude) ||
                double.IsNaN(regionOffset) || double.IsInfinity(regionOffset)) reason = "地区坐标或出生/出口绑定不完整。";
            else if (region == 1 && (!salvage || !salvageSurface || !ramGate || guards == null || guards.Length == 0 || roadBeasts == null || roadBeasts.Length == 0)) reason = "第一地区缺少拾取、撞门或真实敌人。";
            else if (region >= 2 && (!powerPoint || !powerSurface || waves == null || waves.Length == 0 || chargeSeconds <= 0 || float.IsNaN(chargeSeconds) || float.IsInfinity(chargeSeconds))) reason = "供电遭遇缺少真实波次。";
            else if (region == 2 && (!salvage || !salvageSurface)) reason = "第二地区缺少线圈拾取点。";
            else if (region == 3 && !safeZone) reason = "最终地区缺少真实安全区。";
            if (reason == null && region <= 2 && string.IsNullOrWhiteSpace(pickupId)) reason = "拾取物缺少整局唯一 ID。";
            if (reason != null) return false;
            var seen = new HashSet<BeastActor>();
            if (guards != null) foreach (var e in guards) if (!e || !seen.Add(e)) { reason = "守卫引用缺失或重复。"; return false; }
            if (roadBeasts != null) foreach (var e in roadBeasts) if (!e || !seen.Add(e)) { reason = "道路敌人引用缺失或重复。"; return false; }
            if (waves != null) foreach (var wave in waves)
            {
                if (wave == null || wave.enemies == null || wave.enemies.Length == 0) { reason = "空波次不能作为完成证据。"; return false; }
                foreach (var e in wave.enemies) if (!e || !seen.Add(e)) { reason = "波次敌人引用缺失或重复。"; return false; }
            }
            return true;
        }
    }
}
