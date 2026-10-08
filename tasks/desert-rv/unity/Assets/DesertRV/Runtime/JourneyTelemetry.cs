using System;
using System.Collections.Generic;
namespace DesertRV
{
    public enum JourneyActivity { Driving, OnFoot, Reloading, Installing, PoweredDefense }
    [Serializable] public sealed class RegionActivityTime
    {
        public int region;
        public double driving, onFoot, reloading, installing, poweredDefense;
        public double Total => driving + onFoot + reloading + installing + poweredDefense;
    }
    // Exclusive buckets: sums equal actual Playing time, never configured padding.
    public sealed class JourneyTelemetry
    {
        readonly List<RegionActivityTime> regions = new List<RegionActivityTime>();
        public IReadOnlyList<RegionActivityTime> Regions => regions;
        public void Reset() => regions.Clear();
        public void Record(int region, JourneyActivity activity, double seconds)
        {
            if (region < 1 || region > 3 || seconds <= 0 || double.IsNaN(seconds) || double.IsInfinity(seconds)) return;
            var item = regions.Find(r => r.region == region);
            if (item == null) { item = new RegionActivityTime { region = region }; regions.Add(item); }
            switch (activity)
            {
                case JourneyActivity.Driving: item.driving += seconds; break;
                case JourneyActivity.OnFoot: item.onFoot += seconds; break;
                case JourneyActivity.Reloading: item.reloading += seconds; break;
                case JourneyActivity.Installing: item.installing += seconds; break;
                case JourneyActivity.PoweredDefense: item.poweredDefense += seconds; break;
            }
        }
    }
}
