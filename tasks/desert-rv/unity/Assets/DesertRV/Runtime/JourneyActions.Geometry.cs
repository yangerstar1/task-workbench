using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Runtime.CompilerServices;
using UnityEngine;

namespace DesertRV
{
    public sealed partial class JourneyActions
    {
        [Serializable] public sealed class ArcMeshSnapshot
        {
            [SerializeField] internal Mesh mesh;
            [SerializeField] internal Vector3[] vertices;
            [SerializeField] internal int[] triangles;
            [SerializeField] internal string sha256;
            public Mesh SourceMesh => mesh;
            public string Sha256 => sha256;
#if UNITY_EDITOR
            public static ArcMeshSnapshot FromImportedMesh(Mesh source, Vector3[] points, int[] indices)
            {
                var result = new ArcMeshSnapshot { mesh = source, vertices = (Vector3[])points.Clone(), triangles = (int[])indices.Clone() };
                result.sha256 = ArcGeometryDigest(result); ValidateArcGeometry(result); return result;
            }
#endif
        }
        // Only the retained RV's nonconvex colliders. Authored from the immutable imported meshes.
        public ArcMeshSnapshot[] arcMeshGeometry = Array.Empty<ArcMeshSnapshot>();
        sealed class Topology { public string digest; public Mesh mesh; public Vector3[] vertices; public int[] triangles, shells; public bool[] closed, degenerate; }
        static ConditionalWeakTable<ArcMeshSnapshot, Topology> topologyCache = new ConditionalWeakTable<ArcMeshSnapshot, Topology>();
        static bool GeometryFinite(float value) => !float.IsNaN(value) && !float.IsInfinity(value);
        static bool GeometryFinite(Vector3 value) => GeometryFinite(value.x) && GeometryFinite(value.y) && GeometryFinite(value.z);
        public static string ArcGeometryDigest(ArcMeshSnapshot snapshot)
        {
            if (snapshot == null || snapshot.vertices == null || snapshot.triangles == null) throw new InvalidOperationException("Missing arc mesh snapshot.");
            using (var bytes = new MemoryStream())
            using (var writer = new BinaryWriter(bytes))
            {
                writer.Write(snapshot.vertices.Length); writer.Write(snapshot.triangles.Length);
                foreach (var v in snapshot.vertices) { writer.Write(v.x); writer.Write(v.y); writer.Write(v.z); }
                foreach (int index in snapshot.triangles) writer.Write(index);
                writer.Flush();
                using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(bytes.ToArray())).Replace("-", "").ToLowerInvariant();
            }
        }
        static bool ArcGeometryCacheMatches(ArcMeshSnapshot snapshot, Topology ready) => snapshot != null && ready != null && ready.digest == snapshot.sha256 &&
            ready.mesh == snapshot.mesh && ReferenceEquals(ready.vertices, snapshot.vertices) && ReferenceEquals(ready.triangles, snapshot.triangles);
        void OnValidate() { topologyCache = new ConditionalWeakTable<ArcMeshSnapshot, Topology>(); }
        static Topology ValidateArcGeometry(ArcMeshSnapshot snapshot)
        {
            if (snapshot == null || !snapshot.mesh || snapshot.vertices == null || snapshot.triangles == null ||
                snapshot.vertices.Length != snapshot.mesh.vertexCount || snapshot.vertices.Length < 3 || snapshot.triangles.Length < 3 || snapshot.triangles.Length % 3 != 0)
                throw new InvalidOperationException("Missing/mismatched arc mesh geometry.");
            long indexCount = 0;
            for (int sub = 0; sub < snapshot.mesh.subMeshCount; sub++)
            {
                if (snapshot.mesh.GetTopology(sub) != MeshTopology.Triangles) throw new InvalidOperationException("Arc mesh has nontriangle topology.");
                indexCount += (long)snapshot.mesh.GetIndexCount(sub);
            }
            if (indexCount != snapshot.triangles.Length) throw new InvalidOperationException("Arc mesh topology changed.");
            // Player snapshots have no public geometry mutator. Validate once per immutable snapshot/mesh identity.
            // Editor serialization edits clear the cache, and the content gate independently compares every source byte.
#if !UNITY_EDITOR
            if (topologyCache.TryGetValue(snapshot, out var ready) && ArcGeometryCacheMatches(snapshot, ready)) return ready;
#endif
            string digest = ArcGeometryDigest(snapshot);
            if (string.IsNullOrEmpty(snapshot.sha256) || snapshot.sha256 != digest) throw new InvalidOperationException("Arc mesh geometry hash changed.");
            if (topologyCache.TryGetValue(snapshot, out var cached) && ArcGeometryCacheMatches(snapshot, cached)) return cached;
            var welded = new Dictionary<Vector3, int>(); var vertexIds = new int[snapshot.vertices.Length];
            for (int i = 0; i < vertexIds.Length; i++)
            {
                var vertex = snapshot.vertices[i];
                if (!GeometryFinite(vertex)) throw new InvalidOperationException("Nonfinite arc mesh vertex.");
                if (!welded.TryGetValue(vertex, out int id)) { id = welded.Count; welded.Add(vertex, id); }
                vertexIds[i] = id;
            }
            int count = snapshot.triangles.Length / 3; var degenerate = new bool[count]; var parent = new int[count]; var open = new bool[count];
            for (int i = 0; i < count; i++) parent[i] = i;
            int Find(int i) { while (parent[i] != i) { parent[i] = parent[parent[i]]; i = parent[i]; } return i; }
            var edges = new Dictionary<long, List<(int triangle, int direction)>>();
            for (int t = 0; t < count; t++)
            {
                var ids = new int[3];
                for (int j = 0; j < 3; j++)
                {
                    int index = snapshot.triangles[t * 3 + j];
                    if (index < 0 || index >= vertexIds.Length) throw new InvalidOperationException("Arc mesh index out of range.");
                    ids[j] = vertexIds[index];
                }
                var va = snapshot.vertices[snapshot.triangles[t * 3]]; var vb = snapshot.vertices[snapshot.triangles[t * 3 + 1]]; var vc = snapshot.vertices[snapshot.triangles[t * 3 + 2]];
                degenerate[t] = Vector3.Cross(vb - va, vc - va).sqrMagnitude == 0;
                for (int j = 0; j < 3; j++)
                {
                    int a = ids[j], b = ids[(j + 1) % 3]; if (a == b) continue; long key = ((long)Math.Min(a, b) << 32) | (uint)Math.Max(a, b);
                    if (!edges.TryGetValue(key, out var uses)) edges.Add(key, uses = new List<(int, int)>());
                    uses.Add((t, a < b ? 1 : -1));
                }
            }
            foreach (var uses in edges.Values)
            {
                if (uses.Count == 1) { open[uses[0].triangle] = true; continue; }
                if (uses.Count != 2 || uses[0].direction == uses[1].direction) throw new InvalidOperationException("Nonmanifold/inconsistently wound arc mesh.");
                parent[Find(uses[1].triangle)] = Find(uses[0].triangle);
            }
            var shellIds = new Dictionary<int, int>(); var shells = new int[count];
            for (int t = 0; t < count; t++) { int root = Find(t); if (!shellIds.TryGetValue(root, out int id)) { id = shellIds.Count; shellIds.Add(root, id); } shells[t] = id; }
            var closed = new bool[shellIds.Count]; for (int i = 0; i < closed.Length; i++) closed[i] = true;
            for (int t = 0; t < count; t++) if (open[t]) closed[shells[t]] = false;
            var hasArea = new bool[closed.Length];
            for (int t = 0; t < count; t++) if (!degenerate[t]) hasArea[shells[t]] = true;
            for (int i = 0; i < closed.Length; i++) if (!hasArea[i]) closed[i] = false;
            int closedCount = 0; foreach (bool value in closed) if (value) closedCount++;
            if (closedCount > 1) throw new InvalidOperationException("Multiple closed arc shells require an explicit containment proof; not supported by this retained-RV query.");
            cached = new Topology { digest = digest, mesh = snapshot.mesh, vertices = snapshot.vertices, triangles = snapshot.triangles, shells = shells, closed = closed, degenerate = degenerate }; topologyCache.Remove(snapshot); topologyCache.Add(snapshot, cached); return cached;
        }
        static float SegmentDistanceSquared(Vector3 p, Vector3 a, Vector3 b)
        { var ab = b - a; float length = ab.sqrMagnitude; return (p - (a + ab * (length > 0 ? Mathf.Clamp01(Vector3.Dot(p - a, ab) / length) : 0))).sqrMagnitude; }
        static float TriangleDistanceSquared(Vector3 point, Vector3 a, Vector3 b, Vector3 c, bool sourceDegenerate)
        {
            var ab = b - a; var ac = c - a; var n = Vector3.Cross(ab, ac); float nn = n.sqrMagnitude;
            if (!GeometryFinite(nn)) throw new InvalidOperationException("Nonfinite transformed arc triangle.");
            if (sourceDegenerate || nn == 0) return Mathf.Min(SegmentDistanceSquared(point, a, b), Mathf.Min(SegmentDistanceSquared(point, b, c), SegmentDistanceSquared(point, c, a)));
            var projected = point - n * (Vector3.Dot(point - a, n) / nn);
            if (Vector3.Dot(Vector3.Cross(b - a, projected - a), n) >= 0 && Vector3.Dot(Vector3.Cross(c - b, projected - b), n) >= 0 && Vector3.Dot(Vector3.Cross(a - c, projected - c), n) >= 0)
                return (point - projected).sqrMagnitude;
            return Mathf.Min(SegmentDistanceSquared(point, a, b), Mathf.Min(SegmentDistanceSquared(point, b, c), SegmentDistanceSquared(point, c, a)));
        }
        public static float ArcMeshDistanceSquared(ArcMeshSnapshot snapshot, Matrix4x4 toWorld, Vector3 point, out bool inside)
        {
            var topology = ValidateArcGeometry(snapshot); inside = false;
            for (int i = 0; i < 16; i++) if (!GeometryFinite(toWorld[i])) throw new InvalidOperationException("Nonfinite arc collider transform.");
            if (!GeometryFinite(point) || Mathf.Abs(toWorld.determinant) < 1e-12f) throw new InvalidOperationException("Invalid arc point/transform.");
            float nearest = float.PositiveInfinity; double angle = 0;
            for (int t = 0; t < snapshot.triangles.Length / 3; t++)
            {
                var a = toWorld.MultiplyPoint3x4(snapshot.vertices[snapshot.triangles[t * 3]]);
                var b = toWorld.MultiplyPoint3x4(snapshot.vertices[snapshot.triangles[t * 3 + 1]]);
                var c = toWorld.MultiplyPoint3x4(snapshot.vertices[snapshot.triangles[t * 3 + 2]]);
                nearest = Mathf.Min(nearest, TriangleDistanceSquared(point, a, b, c, topology.degenerate[t]));
                if (topology.degenerate[t] || Vector3.Cross(b - a, c - a).sqrMagnitude == 0) continue; // Source zero-area faces contribute real segments/points, never a solid angle.
                if (!topology.closed[topology.shells[t]]) continue; // Open components are two-sided surfaces, not invented solid volumes.
                a -= point; b -= point; c -= point;
                double la = a.magnitude, lb = b.magnitude, lc = c.magnitude;
                double denominator = la * lb * lc + Vector3.Dot(a, b) * lc + Vector3.Dot(b, c) * la + Vector3.Dot(c, a) * lb;
                angle += 2 * Math.Atan2(Vector3.Dot(a, Vector3.Cross(b, c)), denominator);
            }
            if (!GeometryFinite(nearest) || double.IsNaN(angle) || double.IsInfinity(angle)) throw new InvalidOperationException("Invalid arc geometry result.");
            // The one supported closed shell handles concavities/cavities without ray-edge ambiguity. Independent closed shells are rejected during topology validation.
            inside = Math.Abs(angle) > 2 * Math.PI;
            return nearest;
        }
        public bool CheckArcSource(out Collider blocker, out float squareDistance, out string query)
        {
            blocker = null; squareDistance = float.NaN; query = "missing-binding";
            if (!arcOrigin || !motor || !motor.arc || !motor.vehicle || !arcOrigin.IsChildOf(motor.arc.transform) || !GeometryFinite(arcOrigin.position)) return false;
            foreach (var collider in motor.vehicle.GetComponentsInChildren<Collider>(true))
            {
                if (!collider.enabled || collider.isTrigger || !collider.gameObject.activeInHierarchy) continue;
                blocker = collider;
                try
                {
                    if (collider is MeshCollider mesh && !mesh.convex)
                    {
                        query = "nonconvex-triangles"; ArcMeshSnapshot snapshot = null;
                        foreach (var candidate in arcMeshGeometry ?? Array.Empty<ArcMeshSnapshot>()) if (candidate != null && candidate.mesh == mesh.sharedMesh)
                        { if (snapshot != null) throw new InvalidOperationException("Duplicate arc mesh snapshot."); snapshot = candidate; }
                        ValidateArcGeometry(snapshot);
                        var bounds = collider.bounds;
                        if (!GeometryFinite(bounds.center) || !GeometryFinite(bounds.extents)) throw new InvalidOperationException("Nonfinite arc collider bounds.");
                        squareDistance = bounds.SqrDistance(arcOrigin.position);
                        if (GeometryFinite(squareDistance) && squareDistance >= .000001f) { query = "nonconvex-aabb-distance-lower-bound"; continue; }
                        squareDistance = ArcMeshDistanceSquared(snapshot, collider.transform.localToWorldMatrix, arcOrigin.position, out bool inside);
                        if (inside || squareDistance < .000001f) return false;
                    }
                    else if (collider is BoxCollider || collider is SphereCollider || collider is CapsuleCollider || collider is MeshCollider convex && convex.convex)
                    {
                        query = "native-supported-closest-point"; squareDistance = (collider.ClosestPoint(arcOrigin.position) - arcOrigin.position).sqrMagnitude;
                        if (!GeometryFinite(squareDistance) || squareDistance < .000001f) return false;
                    }
                    else { query = "unsupported-solid-collider"; return false; }
                }
                catch (InvalidOperationException) { query += "-invalid-geometry"; return false; }
            }
            blocker = null; squareDistance = float.PositiveInfinity; query = "clear"; return true;
        }
    }
}
