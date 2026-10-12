using Lottery.G3.Core;

namespace Lottery.G3.Ads
{
    public static class SyntheticAdFixture
    {
        public const string Label = "SYNTHETIC_AD_FIXTURE";
        public const int MinimumSettlements = 12, MinimumSeconds = 60, DailySuccessCap = 1, CooldownSettlements = 12;

        // Only creates a new labeled test run. There is no API to mutate a live normal run.
        // Day remains 1: this emulates ad qualifications, not day-2 gameplay or production admission.
        public static RunState Create(string runId, string seed = "g3-synthetic-ad-fixture")
        {
            var s = RunFactory.Create(runId, seed);
            s.FixtureLabel = Label;
            s.FixtureBaseSettlements = s.SettledTicketCount = MinimumSettlements;
            s.FirstLaunchElapsedSeconds = MinimumSeconds;
            s.SettledCountAtLastAdSuccess = -1;
            return s;
        }
    }
}
