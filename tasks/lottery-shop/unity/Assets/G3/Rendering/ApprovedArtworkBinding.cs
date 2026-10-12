// PREPARATION_NOT_STAGE_ADVANCE. Runtime uses an Editor-verified pairing,
// never claims that compressed GPU pixels prove an original PNG SHA.
using System;
using UnityEngine;
namespace Lottery.G3.Rendering
{
    public sealed class ApprovedArtworkBinding : ScriptableObject
    {
        [SerializeField] string artworkId;
        [SerializeField] Texture2D albedo;
        [SerializeField,HideInInspector] Texture2D verifiedTexture;
        [SerializeField,HideInInspector] string verifiedArtworkId,verifiedSourceSha256,verifiedAssetGuid;
        public string ArtworkId => artworkId;
        public Texture2D Albedo => albedo;
        public TicketLayout GetReviewedLayout()
        {
            if(artworkId=="number") return ReviewedLayouts.Number();
            if(artworkId=="challenge") return ReviewedLayouts.Challenge();
            throw new InvalidOperationException("Unreviewed artwork identity");
        }
        public void RequireVerifiedPair()
        {
            var layout=GetReviewedLayout();
            if(albedo==null || albedo!=verifiedTexture || artworkId!=verifiedArtworkId ||
               verifiedSourceSha256!=layout.ArtworkSha256 || string.IsNullOrEmpty(verifiedAssetGuid) ||
               albedo.width!=layout.Width || albedo.height!=layout.Height)
                throw new InvalidOperationException("Artwork pairing/import requires Editor source-SHA validation");
        }
#if UNITY_EDITOR
        public void SetEditorVerification(string sourceSha,string assetGuid)
        {
            if(sourceSha!=GetReviewedLayout().ArtworkSha256 || string.IsNullOrEmpty(assetGuid)) throw new InvalidOperationException("Source identity mismatch");
            verifiedTexture=albedo; verifiedArtworkId=artworkId; verifiedSourceSha256=sourceSha; verifiedAssetGuid=assetGuid;
        }
        public void ClearEditorVerification() { verifiedTexture=null; verifiedArtworkId=null; verifiedSourceSha256=null; verifiedAssetGuid=null; }
#endif
    }
}
