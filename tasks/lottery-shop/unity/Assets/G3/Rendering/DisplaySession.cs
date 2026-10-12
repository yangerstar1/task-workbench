// Display-only capability/revision fence. Not a ledger; never changes saved bits.
using System;
namespace Lottery.G3.Rendering
{
    public sealed class DisplaySession
    {
        public string TicketId { get; private set; }
        public long Revision { get; private set; } = -1;
        public bool Visible { get; private set; }
        Guid activeToken;
        string fingerprint; long minimumRevision;
        // Explicit host recovery/resume creates a NEW token. Callbacks retain the
        // token they started with; they must never substitute a newer token.
        public Guid Begin(string ticketId,long confirmedRevisionFloor)
        {
            Invalidate();
            if(string.IsNullOrEmpty(ticketId) || confirmedRevisionFloor<0)
                throw new ArgumentException("Confirmed ticket identity and revision floor required");
            if(TicketId==ticketId) minimumRevision=Math.Max(minimumRevision,confirmedRevisionFloor);
            else { TicketId=ticketId; minimumRevision=confirmedRevisionFloor; Revision=-1; fingerprint=null; }
            activeToken=Guid.NewGuid(); return activeToken;
        }
        public bool IsCurrent(Guid token,string ticketId,long revision) => activeToken!=Guid.Empty && token==activeToken && TicketId==ticketId && revision>=Revision && revision>=minimumRevision;
        public void Invalidate() { activeToken=Guid.Empty; Visible=false; }
        public bool Commit(Guid token,string ticketId,long revision,string dataFingerprint)
        {
            if(!IsCurrent(token,ticketId,revision)) return false;
            if(revision<0 || string.IsNullOrEmpty(dataFingerprint) || (revision==Revision && fingerprint!=dataFingerprint))
            { Invalidate(); throw new InvalidOperationException("Invalid or conflicting confirmed display revision"); }
            Revision=revision; fingerprint=dataFingerprint; Visible=true; return true;
        }
    }
}
