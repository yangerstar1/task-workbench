using System.Collections.Generic;
using UnityEngine;

namespace DesertRV
{
    // Immutable notifications emitted only after authoritative gameplay succeeds.
    public readonly struct ShotPresentationEvent
    {
        public readonly int Epoch, Sequence;
        public readonly Vector3 End;
        public ShotPresentationEvent(int epoch, int sequence, Vector3 end)
        { Epoch = epoch; Sequence = sequence; End = end; }
    }
    public readonly struct ReloadPresentationEvent
    {
        public readonly int Epoch, Sequence;
        public readonly int LoadedBefore, PlannedAdded;
        public ReloadPresentationEvent(int epoch, int sequence, int loadedBefore, int plannedAdded)
        { Epoch = epoch; Sequence = sequence; LoadedBefore = loadedBefore; PlannedAdded = plannedAdded; }
    }
    public static class ReloadPresentationPlan
    {
        public const int Capacity = 12;
        public static int Added(int loaded, int reserve) => loaded < 0 || loaded > Capacity || reserve < 0 ? 0 : Mathf.Min(Capacity - loaded, reserve);
        // R2 mechanical timing, with an unkeyed carrier offset during actual strip grip.
        public static float GripWeight(float normalized)
        {
            float frame = 1 + Mathf.Clamp01(normalized) * 99;
            if (frame < 30 || frame >= 73) return 0;
            if (frame < 35) return (frame - 30) / 5;
            if (frame <= 68) return 1;
            return (73 - frame) / 5;
        }
    }
    public readonly struct ArcPresentationEvent
    {
        public readonly int Epoch, Sequence, Pulse;
        public readonly BeastActor Target;
        public readonly Vector3 Origin, End;
        public ArcPresentationEvent(int epoch, int sequence, int pulse, BeastActor target, Vector3 origin, Vector3 end)
        { Epoch = epoch; Sequence = sequence; Pulse = pulse; Target = target; Origin = origin; End = end; }
    }
    public sealed class PresentationEventCursor
    {
        int epoch, sequence;
        public void Reset(int currentEpoch) { epoch = currentEpoch; sequence = 0; }
        public bool Consume(int currentEpoch, int eventEpoch, int eventSequence)
        {
            if (currentEpoch != epoch) Reset(currentEpoch);
            if (eventEpoch != currentEpoch || eventSequence <= sequence) return false;
            sequence = eventSequence; return true;
        }
    }
    // One owner per source/channel, including accidentally duplicated prefab instances.
    internal static class PresentationOwnership
    {
        static readonly Dictionary<string, Component> owners = new Dictionary<string, Component>();
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void Reset() => owners.Clear();
        static string Key(Component source, string channel) => source.GetInstanceID() + ":" + channel;
        internal static bool Acquire(Component source, Component owner, string channel)
        {
            string key = Key(source, channel);
            if (owners.TryGetValue(key, out var current) && current && current != owner) return false;
            owners[key] = owner; return true;
        }
        internal static void Release(Component source, Component owner, string channel)
        {
            if (!source) return;
            string key = Key(source, channel);
            if (owners.TryGetValue(key, out var current) && current == owner) owners.Remove(key);
        }
    }
}
