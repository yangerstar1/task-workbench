using System;
using Lottery.G2.Core;
namespace Lottery.G3.Core
{
    public readonly struct CellStroke
    {
        public readonly int CellIndex; public readonly double FromU,FromV,ToU,ToV,RadiusU,RadiusV; public readonly bool HasFrom;
        public CellStroke(int cellIndex,double fromU,double fromV,double toU,double toV,bool hasFrom,double radiusU,double radiusV)
        {CellIndex=cellIndex;FromU=fromU;FromV=fromV;ToU=toU;ToV=toV;HasFrom=hasFrom;RadiusU=radiusU;RadiusV=radiusV;}
    }
    public sealed class TicketMask
    {
        public const int GridWidth=256,GridHeight=128;
        public const string Version="g3-cell-local-mask-256x128-ellipse90-v1";
        readonly byte[] bits;
        public int CellCount {get;} public int Width=>GridWidth; public int Height=>GridHeight;
        public TicketMask(int cellCount):this(cellCount,new byte[GridWidth*GridHeight/8]){}
        public TicketMask(int cellCount,byte[] serialized)
        {if((cellCount!=6&&cellCount!=8)||serialized==null||serialized.Length!=GridWidth*GridHeight/8)throw new ArgumentException("Invalid cell mask");CellCount=cellCount;bits=(byte[])serialized.Clone();}
        public byte[] ToBytes()=>(byte[])bits.Clone();
        public bool IsRevealed(int x,int y)
        {if(x<0||x>=GridWidth||y<0||y>=GridHeight)throw new ArgumentOutOfRangeException();int i=y*GridWidth+x;return (bits[i>>3]&(1<<(i&7)))!=0;}
        public bool IsRevealed(int index) {if(index<0||index>=GridWidth*GridHeight)throw new ArgumentOutOfRangeException();return IsRevealed(index%GridWidth,index/GridWidth);}
        bool Reveal(int x,int y){int i=y*GridWidth+x;byte flag=(byte)(1<<(i&7));bool changed=(bits[i>>3]&flag)==0;bits[i>>3]|=flag;return changed;}
        public ScratchRegion GetCellRegion(int index)
        {if(index<0||index>=CellCount)throw new ArgumentOutOfRangeException(nameof(index));int cols=CellCount/2,x=index%cols*GridWidth/cols,right=(index%cols+1)*GridWidth/cols,y=index/cols*GridHeight/2;return new ScratchRegion(x,y,right-x,GridHeight/2);}
        public int CellRevealedPixels(int cell)
        {var r=GetCellRegion(cell);int n=0;for(int y=r.Y;y<r.Y+r.Height;y++)for(int x=r.X;x<r.X+r.Width;x++)if(IsRevealed(x,y))n++;return n;}
        public double CellCoverage(int cell){var r=GetCellRegion(cell);return (double)CellRevealedPixels(cell)/(r.Width*r.Height);}
        public int RevealedCellCount {get{int n=0;for(int i=0;i<CellCount;i++)if(CellCoverage(i)==1)n++;return n;}}
        public bool IsFullyRevealed=>RevealedCellCount==CellCount;
        public bool RevealCell(int cell)
        {var r=GetCellRegion(cell);bool changed=false;for(int y=r.Y;y<r.Y+r.Height;y++)for(int x=r.X;x<r.X+r.Width;x++)changed|=Reveal(x,y);return changed;}
        public bool RevealAll(){bool changed=false;for(int i=0;i<CellCount;i++)changed|=RevealCell(i);return changed;}
        public bool Apply(CellStroke[] strokes,int allowedCell=-1)
        {
            if(strokes==null||strokes.Length==0||strokes.Length>256)throw new ArgumentException("Invalid brush batch");
            foreach(var s in strokes)
            {
                if(s.CellIndex<0||s.CellIndex>=CellCount||(allowedCell>=0&&s.CellIndex!=allowedCell)||!Inside(s.ToU)||!Inside(s.ToV)||(s.HasFrom&&(!Inside(s.FromU)||!Inside(s.FromV)))||!Radius(s.RadiusU)||!Radius(s.RadiusV))throw new ArgumentException("Invalid cell-local stroke");
            }
            bool changed=false;
            foreach(var s in strokes)
            {
                var r=GetCellRegion(s.CellIndex);double rx=s.RadiusU*r.Width,ry=s.RadiusV*r.Height;
                double x1=r.X+s.ToU*(r.Width-1),y1=r.Y+s.ToV*(r.Height-1),x0=s.HasFrom?r.X+s.FromU*(r.Width-1):x1,y0=s.HasFrom?r.Y+s.FromV*(r.Height-1):y1;
                double dx=x1-x0,dy=y1-y0;int steps=Math.Max(1,(int)Math.Ceiling(Math.Sqrt(dx*dx+dy*dy)/Math.Max(.25,Math.Min(rx,ry)*.5)));
                for(int n=0;n<=steps;n++)
                {
                    double cx=x0+dx*n/steps,cy=y0+dy*n/steps;
                    // Strict target-region clip. No neighboring logical pixel is ever touched.
                    int left=Math.Max(r.X,(int)Math.Floor(cx-rx)),right=Math.Min(r.X+r.Width-1,(int)Math.Ceiling(cx+rx));
                    int bottom=Math.Max(r.Y,(int)Math.Floor(cy-ry)),top=Math.Min(r.Y+r.Height-1,(int)Math.Ceiling(cy+ry));
                    for(int y=bottom;y<=top;y++)for(int x=left;x<=right;x++)if((x-cx)*(x-cx)/(rx*rx)+(y-cy)*(y-cy)/(ry*ry)<=1)changed|=Reveal(x,y);
                }
                if(CellRevealedPixels(s.CellIndex)*10>=r.Width*r.Height*9)changed|=RevealCell(s.CellIndex);
            }
            return changed;
        }
        static bool Inside(double v)=>!double.IsNaN(v)&&!double.IsInfinity(v)&&v>=0&&v<=1;
        static bool Radius(double v)=>!double.IsNaN(v)&&!double.IsInfinity(v)&&v>0&&v<=.5;
    }
}
