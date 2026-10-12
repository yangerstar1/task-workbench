using System;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using Lottery.G3.Core;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace Lottery.G3.Interaction
{
    // An explicit allow-list projection, never a serialized save/face or a command gateway.
    // Capturing, viewing and copying have no persistence or network side effects.
    public sealed class G3QaEvidenceSnapshot
    {
        public readonly bool Available;
        public readonly string Text,DisplayText;
        public G3QaEvidenceSnapshot(bool available,string text,string displayText){Available=available;Text=text;DisplayText=displayText;}
    }
    public static class G3QaEvidence
    {
        public static bool Enabled=>Application.isEditor||Debug.isDebugBuild;
        static readonly CultureInfo Invariant=CultureInfo.InvariantCulture;
        static string Value(object value)=>Convert.ToString(value,Invariant).Replace("\\","\\\\").Replace("\r","\\r").Replace("\n","\\n");
        static void Line(StringBuilder b,string key,object value)=>b.Append(key).Append('=').Append(Value(value??"UNKNOWN")).Append('\n');
        static string RectText(Rect r)=>string.Join(",",new[]{r.x,r.y,r.width,r.height}.Select(x=>x.ToString("0.###",Invariant)));
        static string Known(string value)=>string.IsNullOrEmpty(value)?"UNKNOWN":value;
        static string Positive(int value)=>value>0?value.ToString(Invariant):"UNKNOWN";
        public static G3QaEvidenceSnapshot Capture(RunState state,bool committing,G3SceneView view,G3InputRouter router)
        {
            if(!Enabled)return new G3QaEvidenceSnapshot(false,"","QA evidence is disabled in this build.");
            var b=new StringBuilder();Line(b,"format","G3_READ_ONLY_DEVICE_EVIDENCE_V1");
            Line(b,"snapshotUtc",DateTime.UtcNow.ToString("O",Invariant));
            Line(b,"appVersion",Known(Application.version));Line(b,"buildGUID",Known(Application.buildGUID));Line(b,"package",Known(Application.identifier));
            Line(b,"sourceSha256","UNKNOWN_EXTERNAL_BUILD_RECEIPT_REQUIRED");Line(b,"apkSha256","UNKNOWN_EXTERNAL_PACKAGE_HASH_REQUIRED");
            Line(b,"buildMode",Application.isEditor?"EDITOR_SIMULATED_NOT_DEVICE_ACCEPTANCE":"DEVELOPMENT_QA");
            Line(b,"deviceModel",Known(SystemInfo.deviceModel));Line(b,"deviceOS",Known(SystemInfo.operatingSystem));Line(b,"processor",Known(SystemInfo.processorType));Line(b,"socModel","UNKNOWN_VERIFY_FROM_DEVICE_SPECIFICATION");
            Line(b,"systemMemoryMB",Positive(SystemInfo.systemMemorySize));Line(b,"graphicsDevice",Known(SystemInfo.graphicsDeviceName));Line(b,"graphicsAPI",SystemInfo.graphicsDeviceType);
            Line(b,"screenPixels",Screen.width+"x"+Screen.height);Line(b,"displayResolution",Screen.currentResolution.width+"x"+Screen.currentResolution.height);
            Line(b,"screenSafeAreaXYWH",RectText(Screen.safeArea));Line(b,"orientation",Screen.orientation);
            Line(b,"presentationPixels",view==null?"UNKNOWN":view.PresentationWidth+"x"+view.PresentationHeight);
            Line(b,"presentationSafeAreaXYWH",view==null?"UNKNOWN":RectText(view.PresentationSafeArea));
            var camera=view==null?null:view.SceneCamera;
            Line(b,"cameraPixels",camera==null?"UNKNOWN":camera.pixelWidth+"x"+camera.pixelHeight);
            Line(b,"scaledCameraPixels",camera==null?"UNKNOWN":camera.scaledPixelWidth+"x"+camera.scaledPixelHeight);
            Line(b,"internalPipelineTargetPixels","UNKNOWN_NOT_EXPOSED;camera dimensions and configured scales reported separately");
            Line(b,"cameraPosition",camera==null?"UNKNOWN":string.Join(",",new[]{camera.transform.position.x,camera.transform.position.y,camera.transform.position.z}.Select(x=>x.ToString("R",Invariant))));
            Line(b,"cameraRotationQuaternion",camera==null?"UNKNOWN":string.Join(",",new[]{camera.transform.rotation.x,camera.transform.rotation.y,camera.transform.rotation.z,camera.transform.rotation.w}.Select(x=>x.ToString("R",Invariant))));
            var pipeline=GraphicsSettings.currentRenderPipeline as UniversalRenderPipelineAsset;
            Line(b,"urpRenderScale",pipeline==null?"UNKNOWN":pipeline.renderScale.ToString("0.###",Invariant));
            Line(b,"dynamicResolutionScale",ScalableBufferManager.widthScaleFactor.ToString("0.###",Invariant)+","+ScalableBufferManager.heightScaleFactor.ToString("0.###",Invariant));
            Line(b,"qualityLevel",QualitySettings.GetQualityLevel());Line(b,"targetFrameRate",Application.targetFrameRate);
            Line(b,"inputMode",router==null?"UNKNOWN":router.LastInputSource);Line(b,"recordingMethod","EXTERNAL_OPERATOR_RECORD_REQUIRED");
            string status=committing?"UNAVAILABLE_COMMIT_OR_RECOVERY_PENDING":state==null?"UNAVAILABLE_NO_CONFIRMED_STATE":state.RecoveryRequired||!string.IsNullOrEmpty(state.PendingCommandId)?"UNAVAILABLE_COMMIT_OR_RECOVERY_PENDING":"CONFIRMED";
            if(status=="CONFIRMED")
            {
                // Validation is read-only. Never export placeholder recovery state as confirmed.
                try{StateInvariants.Validate(state);}catch(Exception){status="UNAVAILABLE_INVALID_STATE";}
            }
            Line(b,"stateStatus",status);
            if(status!="CONFIRMED")
            {
                Line(b,"confirmedStateSha256","UNAVAILABLE");Line(b,"stateDetails","WITHHELD_FAIL_CLOSED");
                return new G3QaEvidenceSnapshot(false,b.ToString(),"状态未确认，未导出现金、票或账本。\n"+status+"\n请保留原存档；不会自动恢复或新建局。\n设备信息仍可复制。\n"+b);
            }
            var summary=new StringBuilder();
            Line(b,"runId",state.RunId);Line(b,"schema",state.SchemaVersion);Line(b,"rulesHash",state.RulesHash);
            Line(b,"revision",state.Revision);Line(b,"confirmedStateSha256",StateCodec.ComputeHash(state));
            Line(b,"fixtureLabel",state.FixtureLabel==""?"NATURAL_NEW_RUN":state.FixtureLabel);
            Line(b,"day",state.DayNumber);Line(b,"dayPhase",state.Phase);Line(b,"cashMinor",state.CashMinor);Line(b,"availableCashMinor",state.AvailableCashMinor);
            Line(b,"principalMinor",state.PrincipalMinor);Line(b,"interestDueMinor",state.InterestDueMinor);Line(b,"interestPaidMinor",state.InterestPaidMinor);
            Line(b,"ticketsPurchased",state.TicketsPurchasedToday);Line(b,"settledTickets",state.SettledTicketCount);
            var t=state.CurrentTicket;Line(b,"ticketId",t==null?"NONE":t.Id);
            if(t!=null)
            {
                Line(b,"ticketType",t.TicketType);Line(b,"ticketPhase",t.Phase);Line(b,"ticketPurchaseCommandId",t.PurchaseCommandId);
                Line(b,"maskVersion",TicketMask.Version);Line(b,"maskSha256",StateCodec.HashBytes(t.Scratch.ToBytes()));
                Line(b,"maskPixels",t.Scratch.Width+"x"+t.Scratch.Height);Line(b,"maskCellCount",t.Scratch.CellCount);Line(b,"maskFullyRevealedCellCount",t.Scratch.RevealedCellCount);
                Line(b,"maskRevealedPixelsByCoreCell",string.Join(",",Enumerable.Range(0,t.Scratch.CellCount).Select(i=>t.Scratch.CellRevealedPixels(i).ToString(Invariant))));
                Line(b,"selectionId",t.SelectionId==""?"NONE":t.SelectionId);Line(b,"selectionMarkerSha256_16",SelectionMarker(t));Line(b,"selectedCoreCell",t.SelectedCell);
                Line(b,"selectedVisibleCell",t.SelectedCell<0?"NONE":(((t.SelectedCell+4)%8)+1).ToString(Invariant));
                Line(b,"lockedLayoutFingerprintAlgorithm","HMAC_SHA256_RUN_SECRET_V1");Line(b,"lockedLayoutSha256",LockedLayoutHash(state,t));
                for(int slot=0;slot<3;slot++){var item=t.ConfigurationSnapshot.SingleOrDefault(x=>x.TableSlot==slot);Line(b,"currentConfig.slot"+(slot+1),item==null?"EMPTY":item.ItemId+";level="+item.Level);}
                Line(b,"usedConsumableTypes",string.Join(",",t.UsedConsumableTypes));
                for(int i=0;i<t.ConsumableUses.Count;i++){var use=t.ConsumableUses[i];Line(b,"usedConsumable."+i,use.StockId+";item="+use.ItemId+";quality="+use.Quality+";paidMinor="+use.PurchasePriceMinor);}
            }
            else for(int slot=0;slot<3;slot++)Line(b,"currentConfig.slot"+(slot+1),"NO_TICKET");
            for(int slot=0;slot<3;slot++){string id=state.NextToolIds[slot];Line(b,"nextConfig.slot"+(slot+1),id==""?"EMPTY":id+";level="+state.Tools.Single(x=>x.ItemId==id).Level);}
            for(int i=0;i<state.Stock.Count;i++){var stock=state.Stock[i];Line(b,"stock."+i,stock.StockId+";item="+stock.ItemId+";quality="+stock.Quality+";priceMinor="+stock.PriceMinor+";quantity="+stock.Quantity);}
            for(int i=0;i<state.Drawers.Length;i++){var d=state.Drawers[i];Line(b,"drawer."+i,d==null?"EMPTY":d.StockId+";item="+d.ItemId+";quality="+d.Quality+";paidMinor="+d.PurchasePriceMinor);}
            Line(b,"ledgerCount",state.Ledger.Count);Line(b,"commandReceiptCount",state.Commands.Count);
            Line(b,"rejectedCommandReceipts","UNAVAILABLE_NOT_PERSISTED;record visible refusal and before/after snapshots");
            Line(b,"currencyUnit","0.1_FICTIONAL_GAME_COIN;not real money");
            // The concise on-screen document ends before the potentially long journal.
            summary.Append("QA 只读取证 · 上下滑动，复制完整文本\n").Append(b);
            summary.Append("完整钱包流水和命令回执在复制文本中。\n");
            for(int i=0;i<state.Ledger.Count;i++)
            {
                var row=state.Ledger[i];string k="ledger."+i+".";
                Line(b,k+"commandId",row.CommandId);Line(b,k+"kind",row.Kind);Line(b,k+"referenceId",row.ReferenceId);Line(b,k+"deltaMinor",row.DeltaMinor);Line(b,k+"balanceMinor",row.BalanceMinor);
            }
            for(int i=0;i<state.Commands.Count;i++)
            {
                var receipt=state.Commands[i];string k="receipt."+i+".";
                Line(b,k+"commandId",receipt.CommandId);Line(b,k+"kind",receipt.Kind);Line(b,k+"referenceId",receipt.TicketId);Line(b,k+"revision",receipt.Revision);Line(b,k+"cashDeltaMinor",receipt.CashDeltaMinor);Line(b,k+"code",receipt.Code);Line(b,k+"requestDigest",receipt.RequestDigest);
            }
            Line(b,"hiddenDataPolicy","NO_SEED_NO_NUMBER_FACE_NO_PRIZES_NO_CHALLENGE_OUTCOMES;layout fingerprint only");
            return new G3QaEvidenceSnapshot(true,b.ToString(),summary.ToString());
        }
        public static string SelectionMarker(TicketState t)=>string.IsNullOrEmpty(t?.SelectionId)?"NONE":StateCodec.HashBytes(Encoding.UTF8.GetBytes(t.SelectionId)).Substring(0,16);
        static string LockedLayoutHash(RunState s,TicketState t)
        {
            // An unkeyed hash of eight booleans would reveal the layout via 28 guesses.
            // The run secret is used only as the MAC key, never returned or copied.
            using(var bytes=new MemoryStream())using(var writer=new BinaryWriter(bytes,Encoding.UTF8,true))
            {
                writer.Write("g3-qa-locked-layout-v1");writer.Write(t.Id);writer.Write(t.TicketType);
                if(t.TicketType=="challenge")foreach(bool safe in t.ChallengeSafe)writer.Write(safe);
                else{writer.Write(t.Face.GeneratorVersion);writer.Write(t.Face.WinningNumber);foreach(var cell in t.Face.Cells){writer.Write(cell.Number);writer.Write(cell.PrizeMinor);}}
                writer.Flush();using(var mac=new HMACSHA256(Encoding.UTF8.GetBytes(s.Seed)))return BitConverter.ToString(mac.ComputeHash(bytes.ToArray())).Replace("-","").ToLowerInvariant();
            }
        }
        public static string[] DisplayLines(string text)
        {
            // Bounded line lengths keep both landscape ratios legible without tiny text.
            var lines=new System.Collections.Generic.List<string>();
            foreach(string line in text.Split('\n'))
            {
                var part=new StringBuilder();int columns=0;
                foreach(char c in line){int width=c>127?2:1;if(columns+width>72){lines.Add(part.ToString());part.Clear();columns=0;}part.Append(c);columns+=width;}
                lines.Add(part.ToString());
            }
            return lines.ToArray();
        }
    }
}
