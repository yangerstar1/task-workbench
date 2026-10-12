using System;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text;

namespace Lottery.G2.Core
{
    // Frozen, minimal runtime projection of the approved G1 rules.json. CI checks every value.
    public static class NumberTicketRules
    {
        public const string RulesSha256 = "e959108cb2a4ef080862565de5b87814ccdfae14026204227e767d049bbdf668";
        public const string RulesVersion = "lottery-v4-g1-candidate-001";
        public const string GeneratorVersion = "number-face-n1-sha256-v1";
        public const string EconomicDomain = "economic-awards-v1";
        public const string DisplayDomain = "ticket-display-v1";
        public const int MinorUnitsPerCoin = 10, ProbabilityDenominator = 1000000;
        public const int PriceMinor = 1000, InitialCashMinor = 30000, DailyTicketLimit = 12;
        public const int HiddenCells = 6, NumberMin = 1, NumberMax = 49;
        public const int StockPriceMinor = 800, AdPriceMinor = 400, DrawerSlots = 2;
        public const string StockId = "g2-fixed-boost-coupon-common", StockItemId = "boost_coupon", StockQuality = "common";
        public const int AdMinimumSettlements = 12, AdMinimumSeconds = 60, AdDailySuccessCap = 1, AdCooldownSettlements = 12;
        static readonly long[] Prizes = { 0, 500, 1000, 2000, 5000, 20000, 100000, 1000000 };
        static readonly int[] Weights = { 400000, 200000, 220000, 130000, 47000, 2800, 180, 20 };
        static readonly long[] Distractors = { 500, 1000, 2000, 5000 };
        public static long PrizeForSample(int sample)
        {
            if (sample < 0 || sample >= ProbabilityDenominator) throw new ArgumentOutOfRangeException(nameof(sample));
            int cumulative = 0;
            for (int i = 0; i < Weights.Length; i++) { cumulative += Weights[i]; if (sample < cumulative) return Prizes[i]; }
            throw new InvalidOperationException("Incomplete distribution");
        }
        public static bool IsAllowedPrize(long value) { return Array.IndexOf(Prizes, value) >= 0; }
        public static NumberFace BuildFace(string seed, string ticketId, long rawPrize, string displayDomain = null, int ticketPriceMinor = PriceMinor)
        {
            if (ticketPriceMinor != PriceMinor && ticketPriceMinor != 5000) throw new ArgumentOutOfRangeException(nameof(ticketPriceMinor));
            int scale = ticketPriceMinor / PriceMinor;
            if (rawPrize % scale != 0 || !IsAllowedPrize(rawPrize / scale)) throw new ArgumentOutOfRangeException(nameof(rawPrize));
            var random = new DeterministicStream(seed, displayDomain ?? DisplayDomain + "\0" + ticketId + "\0");
            int publicNumber = NumberMin + random.Next(NumberMax - NumberMin + 1);
            int winningPosition = rawPrize > 0 ? random.Next(HiddenCells) : -1;
            var pool = new List<int>();
            for (int n = NumberMin; n <= NumberMax; n++) if (n != publicNumber) pool.Add(n);
            var cells = new NumberCell[HiddenCells];
            for (int i = 0; i < cells.Length; i++)
            {
                if (i == winningPosition) cells[i] = new NumberCell(publicNumber, rawPrize);
                else { int index = random.Next(pool.Count); int n = pool[index]; pool.RemoveAt(index); cells[i] = new NumberCell(n, Distractors[random.Next(Distractors.Length)] * scale); }
            }
            return new NumberFace { WinningNumber = publicNumber, Cells = cells, GeneratorVersion = GeneratorVersion };
        }
        public static void ValidateFace(NumberFace face, long rawPrize)
        {
            if (face == null || face.GeneratorVersion != GeneratorVersion || face.Cells == null || face.Cells.Length != HiddenCells || !IsAllowedPrize(rawPrize)) throw new InvalidOperationException("Invalid face");
            if (face.WinningNumber < NumberMin || face.WinningNumber > NumberMax) throw new InvalidOperationException("Invalid public number");
            var unique = new HashSet<int>(); int matches = 0;
            foreach (var cell in face.Cells)
            {
                if (cell == null || cell.Number < NumberMin || cell.Number > NumberMax || !unique.Add(cell.Number)) throw new InvalidOperationException("Invalid hidden number");
                if (cell.Number == face.WinningNumber) { matches++; if (cell.PrizeMinor != rawPrize) throw new InvalidOperationException("Wrong award"); }
                else if (Array.IndexOf(Distractors, cell.PrizeMinor) < 0) throw new InvalidOperationException("Invalid neutral distractor");
            }
            if (matches != (rawPrize > 0 ? 1 : 0)) throw new InvalidOperationException("Wrong match count");
        }
    }
    public sealed class NumberCell
    {
        public int Number;
        public long PrizeMinor;
        public NumberCell() { }
        public NumberCell(int number, long prizeMinor) { Number = number; PrizeMinor = prizeMinor; }
    }
    public sealed class NumberFace
    {
        public int WinningNumber;
        public NumberCell[] Cells;
        public string GeneratorVersion;
    }
    // Exact G1 SHA-256 counter/rejection stream. Counter is encoded as 16-byte big endian.
    public sealed class DeterministicStream
    {
        readonly byte[] key;
        public ulong Counter { get; private set; }
        public DeterministicStream(string seed, string domain, ulong counter = 0)
        {
            if (seed == null || domain == null) throw new ArgumentNullException();
            using (var sha = SHA256.Create()) key = sha.ComputeHash(Encoding.UTF8.GetBytes("lottery-sha256-stream-v1\0" + seed + "\0" + domain));
            Counter = counter;
        }
        public int Next(int bound)
        {
            if (bound <= 0) throw new ArgumentOutOfRangeException(nameof(bound));
            ulong remainder = 1;
            for (int i = 0; i < 32; i++) remainder = remainder * 256UL % (ulong)bound; // 2^256 mod bound
            while (true)
            {
                byte[] input = new byte[48]; Buffer.BlockCopy(key, 0, input, 0, 32);
                ulong counter = Counter; Counter = checked(Counter + 1);
                for (int i = 47; i >= 40; i--) { input[i] = (byte)counter; counter >>= 8; }
                byte[] block; using (var sha = SHA256.Create()) block = sha.ComputeHash(input);
                bool highAllOnes = true;
                for (int i = 0; i < 28; i++) if (block[i] != 255) { highAllOnes = false; break; }
                ulong low = ((ulong)block[28] << 24) | ((ulong)block[29] << 16) | ((ulong)block[30] << 8) | block[31];
                if (remainder != 0 && highAllOnes && low >= 4294967296UL - remainder) continue;
                ulong value = 0; foreach (byte b in block) value = (value * 256UL + b) % (ulong)bound;
                return (int)value;
            }
        }
    }
}
