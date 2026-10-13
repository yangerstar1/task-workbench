# 美术与字体来源

- 店内建筑、家具、设备和游戏工具：本次以 Blender Python 原创生成，有倒角与实体厚度；脚本在 source/。
- CreamPlaster、GreenPaint、WarmOak、Terrazzo：本次脚本生成的可复现基础纹理，随机种子固定。用于实际三维材质。
- counter-wood-basecolor.png、painted-plaster-basecolor.png：本次 OpenAI 图像生成模型制作的材质原稿，实际尺寸均为 1254 × 1254。木纹用于实体台面，灰泥原稿保留供比较，不宣称两者均已采用。
- 原创中文店名、海报、服务告示、虚构数字看板、陈列票、报纸版式：make_textures.py 生成，不使用现实彩票官方商标、官方票样或真实开奖数据。
- 中文字体：Noto Sans CJK Regular/Bold（系统预装），SIL Open Font License 1.1；文字已光栅化到原创贴图。字体版权许可附于 FONT_LICENSES.txt。
- 英文字体：DejaVu Sans（系统预装）；DejaVu 字体许可见 FONT_LICENSES.txt。
- 既有项目的 number-ticket-albedo.png 仅在 Blender 检视源场景中以引用方式显示，原图未经修改；游戏运行时继续使用项目中的原图。本资产未重新设计或改写该票面，运行时仍由既有项目负责。

## Runtime subset
This attribution describes the complete authored art package. This runtime source checkpoint includes the selected exported models, texture maps, and material/anchor metadata. Authoring scripts, Blender source, and the unused generated plaster study are not in this runtime subset. The two approved gameplay ticket PNG files and their original provenance remain unchanged.
