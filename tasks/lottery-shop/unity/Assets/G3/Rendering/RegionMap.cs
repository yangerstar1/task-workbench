// G3 integration adapted from reviewed preparation v3. Pure display/input geometry; no game mutations.
using System;
using System.Collections.Generic;

namespace Lottery.G3.Rendering
{
    public readonly struct Uv
    {
        public readonly double U,V;
        public Uv(double u,double v) { U=u; V=v; }
        public bool IsFinite => !double.IsNaN(U) && !double.IsInfinity(U) && !double.IsNaN(V) && !double.IsInfinity(V);
    }
    public readonly struct PixelRect
    {
        public readonly int X,Y,Width,Height;
        public PixelRect(int x,int y,int width,int height) { X=x; Y=y; Width=width; Height=height; }
        // Original image coordinates: top-left inclusive, bottom-right exclusive.
        public bool Contains(double x,double y) => x>=X && x<X+Width && y>=Y && y<Y+Height;
        public Uv Center(int imageWidth,int imageHeight) => new Uv((X+Width*.5)/imageWidth,1-(Y+Height*.5)/imageHeight);
        public Uv Local(Uv paper,int imageWidth,int imageHeight) => new Uv((paper.U*imageWidth-X)/Width,(Y+Height-(1-paper.V)*imageHeight)/Height);
    }
    public sealed class CellRegion
    {
        public string Id { get; }
        public int VisualIndex { get; }
        public int CoreIndex { get; } // Confirmed core index; G3 grids use bottom-left row order.
        public PixelRect Silver { get; }
        public PixelRect Text { get; }
        public PixelRect Hit { get; }
        public CellRegion(string id,int visualIndex,int coreIndex,PixelRect silver,PixelRect text,PixelRect hit)
        { Id=id; VisualIndex=visualIndex; CoreIndex=coreIndex; Silver=silver; Text=text; Hit=hit; }
    }
    public sealed class TextRegion
    {
        public string Id { get; }
        public PixelRect Bounds { get; }
        public TextRegion(string id,PixelRect bounds) { Id=id; Bounds=bounds; }
    }
    public sealed class TicketLayout
    {
        public string Id { get; }
        public string ArtworkSha256 { get; }
        public int Width { get; }
        public int Height { get; }
        public IReadOnlyList<CellRegion> Cells { get; }
        public IReadOnlyList<TextRegion> Labels { get; }
        public TicketLayout(string id,string sha,int width,int height,CellRegion[] cells,TextRegion[] labels)
        { Id=id; ArtworkSha256=sha; Width=width; Height=height; Cells=Array.AsReadOnly((CellRegion[])cells.Clone()); Labels=Array.AsReadOnly((TextRegion[])labels.Clone()); }
        public int HitTest(Uv paper,bool silverOnly=false)
        {
            if(!paper.IsFinite || paper.U<0 || paper.U>1 || paper.V<0 || paper.V>1) return -1;
            double x=paper.U*Width,y=(1-paper.V)*Height;
            for(int i=0;i<Cells.Count;i++) if((silverOnly?Cells[i].Silver:Cells[i].Hit).Contains(x,y)) return i;
            return -1;
        }
        public bool TrySilverLocal(Uv paper,out CellRegion cell,out Uv local)
        {
            int index=HitTest(paper,true);
            if(index<0) { cell=null; local=default; return false; }
            cell=Cells[index]; local=cell.Silver.Local(paper,Width,Height); return true;
        }
    }
    public readonly struct CellBrushProposal
    {
        public readonly string VisualId;
        public readonly int CoreIndex;
        public readonly Uv FromLocal,ToLocal;
        public readonly bool HasFrom;
        // A circular footprint in original paper pixels becomes these local radii.
        // Future authority MUST clip rasterization to this one logical cell.
        public readonly double RadiusLocalU,RadiusLocalV;
        public CellBrushProposal(CellRegion cell,Uv from,Uv to,bool hasFrom,double paperRadius)
        { VisualId=cell.Id; CoreIndex=cell.CoreIndex; FromLocal=from; ToLocal=to; HasFrom=hasFrom; RadiusLocalU=paperRadius/cell.Silver.Width; RadiusLocalV=paperRadius/cell.Silver.Height; }
    }
    // Emits proposals only. Never converts to G2 ScratchStroke and never changes a mask.
    public sealed class RegionPointerTracker
    {
        readonly TicketLayout layout;
        int previous=-1; Uv previousLocal;
        public RegionPointerTracker(TicketLayout layout) { this.layout=layout??throw new ArgumentNullException(nameof(layout)); }
        public void Cancel() { previous=-1; }
        public bool Sample(Uv paper,double radiusPaperPixels,out CellBrushProposal proposal)
        {
            if(double.IsNaN(radiusPaperPixels) || double.IsInfinity(radiusPaperPixels) || radiusPaperPixels<=0) { Cancel(); throw new ArgumentOutOfRangeException(nameof(radiusPaperPixels)); }
            if(!layout.TrySilverLocal(paper,out CellRegion cell,out Uv local)) { Cancel(); proposal=default; return false; }
            proposal=new CellBrushProposal(cell,previousLocal,local,previous==cell.VisualIndex,radiusPaperPixels);
            previous=cell.VisualIndex; previousLocal=local; return true;
        }
    }
    public static class ConfirmedMaskProjection
    {
        public const string SupportedVersion="g2-cpu-mask-256x128-circle90-v1";
        public const int Width=256,Height=128,ByteCount=4096;
        public static PixelRect LogicalCell(int coreIndex)
        {
            if(coreIndex<0 || coreIndex>=6) throw new ArgumentOutOfRangeException(nameof(coreIndex));
            int column=coreIndex%3,row=coreIndex/3,left=column*Width/3,right=(column+1)*Width/3;
            // This PixelRect has logical-mask BOTTOM-left coordinates, not artwork coordinates.
            return new PixelRect(left,row*64,right-left,64);
        }
        public static byte[] CopyCell(byte[] confirmedBits,string maskVersion,int coreIndex)
        {
            if(maskVersion!=SupportedVersion) throw new NotSupportedException("Mask version needs explicit recovery compatibility review");
            if(confirmedBits==null || confirmedBits.Length!=ByteCount) throw new ArgumentException("Expected unchanged confirmed 256x128 bitset");
            var r=LogicalCell(coreIndex); var pixels=new byte[r.Width*r.Height];
            for(int y=0;y<r.Height;y++) for(int x=0;x<r.Width;x++)
            {
                int bit=(r.Y+y)*Width+r.X+x;
                pixels[y*r.Width+x]=(confirmedBits[bit>>3]&(1<<(bit&7)))!=0?(byte)255:(byte)0;
            }
            return pixels; // Bottom row first, suitable for Texture2D.SetPixels32.
        }
    }
}
