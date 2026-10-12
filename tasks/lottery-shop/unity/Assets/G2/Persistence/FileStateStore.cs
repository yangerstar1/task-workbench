using System;
using System.IO;
using System.Linq;
using System.Text;
using Lottery.G2.Core;
namespace Lottery.G2.Persistence
{
    public enum StoreFaultPoint { BeforeWrite, TempHalfWritten, TempFlushed, BeforePublish, AfterPublish, BeforeResponse, BeforeRecoveryRead }
    public interface IStoreFaultInjector { void OnPoint(StoreFaultPoint point); }
    // Single-writer, same-directory replace. Process-kill tests do not establish power-loss/filesystem guarantees.
    public sealed class FileStateStore : IStateStore, IDisposable
    {
        readonly object sync = new object();
        readonly string directory, statePath, previousPath, intentPath, markerPath, pendingPath;
        readonly IStoreFaultInjector faults;
        FileStream writerLock;
        RunState confirmed;
        string confirmedHash, pendingCommand = "";
        bool recoveryRequired, unknown, disposed;
        public FileStateStore(string directory, RunState initialState, IStoreFaultInjector faults = null)
        {
            this.directory = directory ?? throw new ArgumentNullException(nameof(directory)); this.faults = faults;
            statePath = Path.Combine(directory, "state.bin"); previousPath = Path.Combine(directory, "previous.bin"); intentPath = Path.Combine(directory, "intent.record"); markerPath = Path.Combine(directory, "commit.record"); pendingPath = Path.Combine(directory, "state.pending");
            confirmed = initialState?.Copy() ?? throw new ArgumentNullException(nameof(initialState));
            Directory.CreateDirectory(directory);
            try
            {
                writerLock = new FileStream(Path.Combine(directory, "writer.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
                bool existing = Directory.GetFiles(directory).Any(p => Path.GetFileName(p) != "writer.lock");
                if (!existing)
                {
                    StateInvariants.Validate(confirmed); var bytes = StateCodec.SerializeCanonical(confirmed); confirmedHash = StateCodec.HashBytes(bytes);
                    WriteFlushed(pendingPath, Wrap(bytes)); File.Move(pendingPath, statePath); WriteAtomic(markerPath, Encoding.UTF8.GetBytes(confirmed.Revision + "\n" + confirmedHash));
                }
                else ReloadDisk(false);
            }
            catch (Exception e) when (IsStorageFailure(e)) { recoveryRequired = true; }
        }
        public string ConfirmedHash { get { lock (sync) return confirmedHash ?? ""; } }
        public bool CanMutate { get { lock (sync) return !disposed && !recoveryRequired && !unknown && writerLock != null && (confirmed.Ad == null || confirmed.Ad.Phase != AdPhase.RECOVERY_CONFLICT); } }
        public RunState Read()
        {
            lock (sync) { var copy = confirmed.Copy(); copy.PendingCommandId = pendingCommand; copy.RecoveryRequired = recoveryRequired || (confirmed.Ad != null && confirmed.Ad.Phase == AdPhase.RECOVERY_CONFLICT); return copy; }
        }
        public CommandResult Execute(string commandId, string requestDigest, long expectedRevision, Func<RunState, CommandReceipt> apply)
        {
            lock (sync)
            {
                if (disposed || recoveryRequired || writerLock == null) return Result(CommitStatus.COMMIT_UNKNOWN, "RECOVERY_REQUIRED");
                if (!ValidId(commandId) || requestDigest == null || requestDigest.Length != 64 || apply == null) return Result(CommitStatus.PROVEN_NOT_COMMITTED, "INVALID_REQUEST");
                // Journal lookup always precedes revision/eligibility checks, even for stale retries.
                var old = confirmed.Commands.SingleOrDefault(c => c.CommandId == commandId);
                if (old != null) return old.RequestDigest == requestDigest ? Result(CommitStatus.COMMITTED, old.Code, old) : Result(CommitStatus.PROVEN_NOT_COMMITTED, "COMMAND_ID_REUSED");
                if (unknown) return Result(CommitStatus.COMMIT_UNKNOWN, "COMMIT_UNKNOWN");
                if (confirmed.Ad != null && confirmed.Ad.Phase == AdPhase.RECOVERY_CONFLICT) return Result(CommitStatus.PROVEN_NOT_COMMITTED, "RECOVERY_REQUIRED");
                if (confirmed.Revision != expectedRevision) return Result(CommitStatus.PROVEN_NOT_COMMITTED, "STALE_REVISION");
                RunState next = confirmed.Copy(); CommandReceipt receipt;
                try
                {
                    receipt = apply(next); if (receipt == null) throw new RuleViolation("INVALID_REQUEST");
                    receipt.CommandId = commandId; receipt.RequestDigest = requestDigest; receipt.Revision = checked(confirmed.Revision + 1); receipt.Code = "SUCCESS";
                    next.Revision = receipt.Revision; next.Commands.Add(receipt); StateInvariants.Validate(next);
                }
                catch (RuleViolation e) { return Result(CommitStatus.PROVEN_NOT_COMMITTED, e.Code); }
                byte[] payload = StateCodec.SerializeCanonical(next); string nextHash = StateCodec.HashBytes(payload);
                pendingCommand = commandId;
                try
                {
                    faults?.OnPoint(StoreFaultPoint.BeforeWrite);
                    WriteAtomic(intentPath, Encoding.UTF8.GetBytes(commandId + "\n" + requestDigest + "\n" + confirmed.Revision + "\n" + confirmedHash + "\n" + next.Revision + "\n" + nextHash));
                    byte[] wrapped = Wrap(payload);
                    using (var f = new FileStream(pendingPath, FileMode.Create, FileAccess.Write, FileShare.None))
                    {
                        int half = wrapped.Length / 2; f.Write(wrapped, 0, half); f.Flush(true); faults?.OnPoint(StoreFaultPoint.TempHalfWritten);
                        f.Write(wrapped, half, wrapped.Length - half); f.Flush(true);
                    }
                    faults?.OnPoint(StoreFaultPoint.TempFlushed); faults?.OnPoint(StoreFaultPoint.BeforePublish);
                    File.Replace(pendingPath, statePath, previousPath);
                    faults?.OnPoint(StoreFaultPoint.AfterPublish);
                    // Read back the published payload before advancing the confirmed high-water mark.
                    byte[] published = Unwrap(File.ReadAllBytes(statePath));
                    if (StateCodec.HashBytes(published) != nextHash) throw new InvalidDataException("Published state differs from intent");
                    WriteAtomic(markerPath, Encoding.UTF8.GetBytes(next.Revision + "\n" + nextHash));
                    ArchiveIntent();
                    faults?.OnPoint(StoreFaultPoint.BeforeResponse);
                    confirmed = next; confirmedHash = nextHash; pendingCommand = ""; unknown = false;
                    return Result(CommitStatus.COMMITTED, "SUCCESS", receipt);
                }
                catch (Exception e) when (IsStorageFailure(e))
                {
                    unknown = true;
                    // An exception is not evidence of failure. The durable journal is authoritative.
                    return Resolve(commandId);
                }
            }
        }
        public CommandResult Recover(string commandId)
        {
            lock (sync)
            {
                if (disposed || writerLock == null) return Result(CommitStatus.COMMIT_UNKNOWN, "RECOVERY_REQUIRED");
                if (!ValidId(commandId)) return Result(CommitStatus.PROVEN_NOT_COMMITTED, "INVALID_REQUEST");
                if (pendingCommand != "" && pendingCommand != commandId) return Result(CommitStatus.COMMIT_UNKNOWN, recoveryRequired ? "RECOVERY_REQUIRED" : "COMMIT_UNKNOWN");
                return Resolve(commandId);
            }
        }
        CommandResult Resolve(string commandId)
        {
            try
            {
                ReloadDisk(true);
                var record = confirmed.Commands.SingleOrDefault(c => c.CommandId == commandId);
                return record != null ? Result(CommitStatus.COMMITTED, record.Code, record) : Result(CommitStatus.PROVEN_NOT_COMMITTED, "SAVE_NOT_COMMITTED");
            }
            catch (InvalidDataException) { recoveryRequired = true; unknown = true; return Result(CommitStatus.COMMIT_UNKNOWN, "RECOVERY_REQUIRED"); }
            catch (Exception e) when (IsStorageFailure(e)) { unknown = true; return Result(CommitStatus.COMMIT_UNKNOWN, "COMMIT_UNKNOWN"); }
        }
        void ReloadDisk(bool inject)
        {
            if (inject) faults?.OnPoint(StoreFaultPoint.BeforeRecoveryRead);
            if (!File.Exists(statePath) || !File.Exists(markerPath)) throw new InvalidDataException("Missing current state/confirmed high-water mark; backup not silently restored");
            byte[] payload = Unwrap(File.ReadAllBytes(statePath)); string hash = StateCodec.HashBytes(payload);
            RunState disk;
            try { disk = StateCodec.DeserializeCanonical(payload); StateInvariants.Validate(disk); }
            catch (Exception e) when (e is InvalidOperationException || e is ArgumentException || e is EndOfStreamException || e is OverflowException) { throw new InvalidDataException("Invalid ledger", e); }
            string[] marker = Encoding.UTF8.GetString(Unwrap(File.ReadAllBytes(markerPath))).Split('\n');
            if (marker.Length != 2 || !long.TryParse(marker[0], out long markedRevision)) throw new InvalidDataException("Invalid commit record");
            if (File.Exists(intentPath))
            {
                string[] intent = Encoding.UTF8.GetString(Unwrap(File.ReadAllBytes(intentPath))).Split('\n');
                if (intent.Length != 6 || !long.TryParse(intent[2], out long baseRevision) || !long.TryParse(intent[4], out long newRevision) || newRevision != baseRevision + 1) throw new InvalidDataException("Invalid intent record");
                pendingCommand = intent[0];
                if (disk.Revision == newRevision && hash == intent[5])
                {
                    var receipt = disk.Commands.SingleOrDefault(c => c.CommandId == intent[0]);
                    if (receipt == null || receipt.RequestDigest != intent[1] || receipt.Revision != newRevision || !((markedRevision == baseRevision && marker[1] == intent[3]) || (markedRevision == newRevision && marker[1] == hash))) throw new InvalidDataException("Commit evidence mismatch");
                    WriteAtomic(markerPath, Encoding.UTF8.GetBytes(newRevision + "\n" + hash)); ArchiveIntent();
                }
                else if (disk.Revision == baseRevision && hash == intent[3] && markedRevision == baseRevision && marker[1] == hash)
                {
                    // Atomic publication has not happened. Preserve the rejected intent/temp for diagnosis.
                    if (File.Exists(pendingPath)) { string failed = Path.Combine(directory, "last-uncommitted.pending"); if (File.Exists(failed)) File.Replace(pendingPath, failed, null); else File.Move(pendingPath, failed); }
                    ArchiveIntent();
                }
                else throw new InvalidDataException("Ambiguous publish or rollback; preserve both snapshots");
            }
            else if (markedRevision != disk.Revision || marker[1] != hash) throw new InvalidDataException("Confirmed high-water mark mismatch; no fallback to older snapshot");
            confirmed = disk; confirmedHash = hash; pendingCommand = ""; unknown = false; recoveryRequired = false;
        }
        void ArchiveIntent()
        {
            if (!File.Exists(intentPath)) return;
            string archive = Path.Combine(directory, "last-intent.record");
            if (File.Exists(archive)) File.Replace(intentPath, archive, null); else File.Move(intentPath, archive);
        }
        static bool ValidId(string id) => !string.IsNullOrWhiteSpace(id) && id.Length <= 256 && !id.Any(char.IsControl);
        CommandResult Result(CommitStatus status, string code, CommandReceipt receipt = null)
        {
            var state = Read(); var copiedReceipt = receipt == null ? null : state.Commands.SingleOrDefault(c => c.CommandId == receipt.CommandId);
            return new CommandResult { CommitStatus = status, Code = code, Receipt = copiedReceipt, State = state };
        }
        static bool IsStorageFailure(Exception e) => e is IOException || e is UnauthorizedAccessException || e is InvalidOperationException || e is System.Security.SecurityException || e is NotSupportedException;
        static byte[] Wrap(byte[] payload)
        {
            using (var stream = new MemoryStream()) using (var w = new BinaryWriter(stream))
            { w.Write("LOTTERY-G2-CHECKSUM-v1"); w.Write(payload.Length); w.Write(StateCodec.HashBytes(payload)); w.Write(payload); w.Flush(); return stream.ToArray(); }
        }
        static byte[] Unwrap(byte[] bytes)
        {
            if (bytes == null || bytes.Length > 17 * 1024 * 1024) throw new InvalidDataException("Invalid envelope size");
            using (var stream = new MemoryStream(bytes)) using (var r = new BinaryReader(stream))
            {
                if (r.ReadString() != "LOTTERY-G2-CHECKSUM-v1") throw new InvalidDataException("Wrong envelope");
                int length = r.ReadInt32(); if (length < 0 || length > 16 * 1024 * 1024) throw new InvalidDataException("Invalid payload length");
                string checksum = r.ReadString(); byte[] payload = r.ReadBytes(length);
                if (payload.Length != length || stream.Position != stream.Length || checksum != StateCodec.HashBytes(payload)) throw new InvalidDataException("Checksum mismatch");
                return payload;
            }
        }
        static void WriteFlushed(string path, byte[] bytes)
        { using (var f = new FileStream(path, FileMode.Create, FileAccess.Write, FileShare.None)) { f.Write(bytes, 0, bytes.Length); f.Flush(true); } }
        static void WriteAtomic(string path, byte[] payload)
        {
            string temp = path + ".new"; WriteFlushed(temp, Wrap(payload));
            if (File.Exists(path)) File.Replace(temp, path, path + ".previous"); else File.Move(temp, path);
        }
        public void Dispose()
        {
            lock (sync) { if (disposed) return; disposed = true; writerLock?.Dispose(); writerLock = null; }
        }
    }
}
