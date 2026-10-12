using System;
namespace Lottery.G2.Core
{
    public readonly struct ScratchStroke
    {
        public readonly double FromU, FromV, ToU, ToV, RadiusPixels;
        public readonly bool HasFrom;
        public ScratchStroke(double fromU, double fromV, double toU, double toV, bool hasFrom, double radiusPixels)
        { FromU = fromU; FromV = fromV; ToU = toU; ToV = toV; HasFrom = hasFrom; RadiusPixels = radiusPixels; }
    }
    public readonly struct ScratchRegion
    {
        public readonly int X, Y, Width, Height;
        public ScratchRegion(int x, int y, int width, int height) { X = x; Y = y; Width = width; Height = height; }
    }
    public sealed class ScratchMask
    {
        public const string Version = "g2-cpu-mask-256x128-circle90-v1";
        public const int GridWidth = 256, GridHeight = 128, Columns = 3, Rows = 2;
        readonly byte[] bits;
        public int Width => GridWidth;
        public int Height => GridHeight;
        public ScratchMask() { bits = new byte[GridWidth * GridHeight / 8]; }
        public ScratchMask(byte[] serialized)
        {
            if (serialized == null || serialized.Length != GridWidth * GridHeight / 8) throw new ArgumentException("Invalid mask size");
            bits = (byte[])serialized.Clone();
        }
        public byte[] ToBytes() => (byte[])bits.Clone();
        public bool IsRevealed(int x, int y) => IsRevealed(CheckedIndex(x, y));
        public bool IsRevealed(int index)
        {
            if (index < 0 || index >= GridWidth * GridHeight) throw new ArgumentOutOfRangeException(nameof(index));
            return (bits[index >> 3] & (1 << (index & 7))) != 0;
        }
        static int CheckedIndex(int x, int y)
        {
            if (x < 0 || x >= GridWidth || y < 0 || y >= GridHeight) throw new ArgumentOutOfRangeException();
            return y * GridWidth + x;
        }
        bool Reveal(int x, int y)
        { int i = y * GridWidth + x; byte flag = (byte)(1 << (i & 7)); bool changed = (bits[i >> 3] & flag) == 0; bits[i >> 3] |= flag; return changed; }
        public static ScratchRegion GetCellRegion(int index)
        {
            if (index < 0 || index >= 6) throw new ArgumentOutOfRangeException(nameof(index));
            int column = index % Columns, row = index / Columns;
            int x = column * GridWidth / Columns, right = (column + 1) * GridWidth / Columns;
            int y = row * GridHeight / Rows, top = (row + 1) * GridHeight / Rows;
            return new ScratchRegion(x, y, right - x, top - y);
        }
        public int CellRevealedPixels(int index)
        {
            var r = GetCellRegion(index); int count = 0;
            for (int y = r.Y; y < r.Y + r.Height; y++) for (int x = r.X; x < r.X + r.Width; x++) if (IsRevealed(x, y)) count++;
            return count;
        }
        public double CellCoverage(int index) { var r = GetCellRegion(index); return (double)CellRevealedPixels(index) / (r.Width * r.Height); }
        public int RevealedCellCount { get { int n = 0; for (int i = 0; i < 6; i++) if (CellCoverage(i) == 1) n++; return n; } }
        public bool IsFullyRevealed => RevealedCellCount == 6;
        public bool Apply(ScratchStroke[] strokes)
        {
            if (strokes == null || strokes.Length > 256) throw new ArgumentException("Invalid brush batch");
            // Validate the whole batch before modifying anything.
            foreach (var s in strokes)
            {
                if (!Inside(s.ToU) || !Inside(s.ToV) || (s.HasFrom && (!Inside(s.FromU) || !Inside(s.FromV))) || double.IsNaN(s.RadiusPixels) || s.RadiusPixels < 1 || s.RadiusPixels > 16)
                    throw new ArgumentException("Brush outside supported bounds");
            }
            bool changed = false;
            foreach (var s in strokes)
            {
                double x1 = s.ToU * (GridWidth - 1), y1 = s.ToV * (GridHeight - 1);
                double x0 = s.HasFrom ? s.FromU * (GridWidth - 1) : x1, y0 = s.HasFrom ? s.FromV * (GridHeight - 1) : y1;
                double dx = x1 - x0, dy = y1 - y0;
                int steps = Math.Max(1, (int)Math.Ceiling(Math.Sqrt(dx * dx + dy * dy) / Math.Max(0.5, s.RadiusPixels * 0.5)));
                for (int n = 0; n <= steps; n++)
                {
                    double x = x0 + dx * n / steps, y = y0 + dy * n / steps, radius2 = s.RadiusPixels * s.RadiusPixels;
                    int left = Math.Max(0, (int)Math.Floor(x - s.RadiusPixels)), right = Math.Min(GridWidth - 1, (int)Math.Ceiling(x + s.RadiusPixels));
                    int bottom = Math.Max(0, (int)Math.Floor(y - s.RadiusPixels)), top = Math.Min(GridHeight - 1, (int)Math.Ceiling(y + s.RadiusPixels));
                    for (int py = bottom; py <= top; py++) for (int px = left; px <= right; px++) if ((px - x) * (px - x) + (py - y) * (py - y) <= radius2) changed |= Reveal(px, py);
                }
            }
            // Finishing a cell is part of the same committed bitset, never a separate UI trick.
            for (int cell = 0; cell < 6; cell++)
            {
                var r = GetCellRegion(cell);
                if (CellRevealedPixels(cell) * 10 >= r.Width * r.Height * 9)
                    for (int y = r.Y; y < r.Y + r.Height; y++) for (int x = r.X; x < r.X + r.Width; x++) changed |= Reveal(x, y);
            }
            return changed;
        }
        static bool Inside(double value) => !double.IsNaN(value) && value >= 0 && value <= 1;
    }
}
