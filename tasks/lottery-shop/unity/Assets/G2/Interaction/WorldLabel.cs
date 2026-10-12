using System.Collections.Generic;
using UnityEngine;

namespace Lottery.G2.Interaction
{
    // Real font-atlas geometry, rendered by the same URP camera as the ticket.
    // No IMGUI, OS font fallback, or text baked by the test runner.
    public sealed class WorldLabel : MonoBehaviour
    {
        const int RasterSize = 64;
        Font font;
        Material material;
        Mesh mesh;
        string value = "";
        float emHeight;
        Color color;
        TextAnchor anchor;
        bool dirty;
        public string Text => value;
        public void Initialize(Font source, Material shared, float height, Color tint, TextAnchor alignment)
        {
            font = source; material = shared; emHeight = height; color = tint; anchor = alignment;
            mesh = new Mesh { name = "G2 licensed glyph geometry" };
            gameObject.AddComponent<MeshFilter>().sharedMesh = mesh;
            gameObject.AddComponent<MeshRenderer>().sharedMaterial = material;
            Font.textureRebuilt += OnAtlasRebuilt;
        }
        public void SetText(string text, float height = -1)
        {
            if (height > 0 && !Mathf.Approximately(height, emHeight)) { emHeight = height; dirty = true; }
            if (value != text) { value = text ?? ""; dirty = true; }
            RebuildIfNeeded();
        }
        public void RebuildIfNeeded()
        {
            if (!dirty || font == null || mesh == null) return;
            dirty = false;
            font.RequestCharactersInTexture(value, RasterSize, FontStyle.Normal);
            var vertices = new List<Vector3>(); var uv = new List<Vector2>();
            var colors = new List<Color>(); var triangles = new List<int>();
            float scale = emHeight / RasterSize, x = 0, y = 0;
            foreach (char c in value)
            {
                if (c == '\n') { x = 0; y -= emHeight * 1.35f; continue; }
                if (!font.GetCharacterInfo(c, out CharacterInfo glyph, RasterSize, FontStyle.Normal)) continue;
                int n = vertices.Count;
                vertices.Add(new Vector3(x + glyph.minX * scale, y + glyph.minY * scale, 0));
                vertices.Add(new Vector3(x + glyph.maxX * scale, y + glyph.minY * scale, 0));
                vertices.Add(new Vector3(x + glyph.maxX * scale, y + glyph.maxY * scale, 0));
                vertices.Add(new Vector3(x + glyph.minX * scale, y + glyph.maxY * scale, 0));
                uv.Add(glyph.uvBottomLeft); uv.Add(glyph.uvBottomRight); uv.Add(glyph.uvTopRight); uv.Add(glyph.uvTopLeft);
                for (int i = 0; i < 4; i++) colors.Add(color);
                triangles.AddRange(new[] { n, n + 2, n + 1, n, n + 3, n + 2 });
                x += glyph.advance * scale;
            }
            if (vertices.Count > 0)
            {
                var bounds = new Bounds(vertices[0], Vector3.zero);
                foreach (var v in vertices) bounds.Encapsulate(v);
                int column = (int)anchor % 3, row = (int)anchor / 3;
                float offsetX = column == 0 ? bounds.min.x : column == 1 ? bounds.center.x : bounds.max.x;
                float offsetY = row == 0 ? bounds.max.y : row == 1 ? bounds.center.y : bounds.min.y;
                var offset = new Vector3(offsetX, offsetY, 0);
                for (int i = 0; i < vertices.Count; i++) vertices[i] -= offset;
            }
            mesh.Clear(); mesh.SetVertices(vertices); mesh.SetUVs(0, uv); mesh.SetColors(colors); mesh.SetTriangles(triangles, 0); mesh.RecalculateBounds();
            material.mainTexture = font.material.mainTexture;
        }
        void OnAtlasRebuilt(Font rebuilt) { if (rebuilt == font) dirty = true; }
        void LateUpdate() { RebuildIfNeeded(); }
        void OnDestroy() { Font.textureRebuilt -= OnAtlasRebuilt; if (mesh != null) Destroy(mesh); }
    }
}
