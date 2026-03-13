# videoskill

`videoskill` 是一个面向 Codex 的本地 skill 仓库。当前仓库包含一个核心 skill：`project-promo-video`，用于在用户项目完成后，运行项目、抓取界面截图，并基于 Remotion 生成带配音和配乐的宣传片。

这个仓库不是一个单独的 Web 应用，而是一套可复用的 skill、脚本和 Remotion 模板。

## 能力概览

- 运行已完成的本地项目并准备截图工作流
- 基于真实 UI 截图生成宣传片结构
- 生成 Remotion 工作目录和场景数据
- 支持 Edge TTS 场景配音
- 支持可选背景音乐接入
- 支持背景音乐淡入淡出和旁白期间自动压混
- 输出可渲染的 `mp4` 宣传片模板

## 仓库结构

```text
videoskill/
├── README.md
└── project-promo-video/
    ├── SKILL.md
    ├── agents/
    │   └── openai.yaml
    ├── scripts/
    │   ├── bootstrap_promo_project.py
    │   └── generate_voiceover_edge.py
    ├── references/
    │   ├── audio-notes.md
    │   └── remotion-notes.md
    └── assets/
        └── remotion-template/
```

## Skill 说明

`project-promo-video` 的目标是把一个已经完成的产品项目转成宣传片素材流：

1. 运行项目
2. 采集高质量产品截图
3. 生成宣传片文案和场景配置
4. 可选生成旁白音频
5. 可选接入背景音乐
6. 在 Remotion 中渲染成片

适用项目：

- SaaS
- Dashboard
- Admin Panel
- Landing Page
- Web App
- 桌面风格产品界面

不适用场景：

- 已有真人实拍素材、需要传统剪辑的项目
- 纯视频素材拼接而非截图驱动的项目

## 安装到 Codex

把 skill 目录复制到你的 Codex skills 目录中即可。常见方式是保留当前仓库，然后让 Codex 直接读取这个 skill。

如果你想手动安装，可复制：

```text
project-promo-video/
```

到你的 Codex skills 目录。

## 依赖要求

基础要求：

- Node.js 18+
- Python 3.8+
- `ffprobe`

如果要生成配音，还需要：

```bash
pip install edge-tts
```

## 快速开始

### 1. 准备截图

先运行你自己的项目，并采集 5-8 张高质量截图，建议命名为：

```text
01-home.png
02-workflow.png
03-results.png
```

### 2. 生成 Remotion 工作目录

```bash
python project-promo-video/scripts/bootstrap_promo_project.py \
  --workspace F:\path\to\promo-workspace \
  --screenshots F:\path\to\screenshots \
  --project-name "Acme" \
  --tagline "Close work faster" \
  --bgm-file F:\path\to\music.mp3 \
  --accent "#14b8a6"
```

这个脚本会：

- 复制 Remotion 模板
- 写入 `src/promo-data.ts`
- 写入 `src/audio-config.ts`
- 生成 `public/audio/voiceover-script.json`
- 复制截图和可选 BGM 文件

### 3. 生成配音

```bash
python project-promo-video/scripts/generate_voiceover_edge.py \
  --workspace F:\path\to\promo-workspace
```

说明：

- 默认支持 `--voice auto`
- 如果文案是中文，会优先选择中文 Edge 声线
- 如果文案是英文，会自动切到英文 Edge 声线
- 生成完成后会自动改写 `src/audio-config.ts`

### 4. 渲染预览或导出

进入生成后的工作目录：

```bash
npm install
npm run start
npm run render
```

默认输出：

```text
out/product-promo.mp4
```

## 音频设计

当前模板已经支持：

- 场景级配音
- 可选背景音乐
- 背景音乐开头淡入
- 背景音乐结尾淡出
- 配音场景期间自动压低背景音乐

这使得宣传片默认更接近可交付状态，而不是只有无声动效。

## 可编辑文件

最常改的文件如下：

- `project-promo-video/SKILL.md`
  skill 主说明
- `project-promo-video/scripts/bootstrap_promo_project.py`
  生成宣传片工作目录
- `project-promo-video/scripts/generate_voiceover_edge.py`
  生成配音并回写时序
- `project-promo-video/assets/remotion-template/src/promo-data.ts`
  宣传片文案、截图和品牌配置
- `project-promo-video/assets/remotion-template/src/audio-config.ts`
  场景时长和旁白时序
- `project-promo-video/assets/remotion-template/src/components/ProductPromo.tsx`
  画面和音频混合逻辑

## 参考项目

本仓库实现时参考了这些项目和资料：

- [andchir/remotion-animations](https://github.com/andchir/remotion-animations)
- [wshuyi/remotion-video-skill](https://github.com/wshuyi/remotion-video-skill)
- [OpenGameArt](https://opengameart.org/)

其中：

- `andchir/remotion-animations` 提供了 Remotion 组合式动画结构参考
- `wshuyi/remotion-video-skill` 提供了按场景生成旁白并回写时序的思路
- OpenGameArt 适合作为开源背景音乐来源之一，但实际交付时要记录许可证

## 当前状态

当前仓库已经包含：

- 完整 skill 目录
- Remotion 宣传片模板
- Edge TTS 配音脚本
- 音乐接入和自动压混逻辑
- GitHub 可直接浏览的项目说明

如果你后续要扩展，可以继续加：

- 中文宣传口播模板
- 多语言文案生成
- 自动截图脚本
- 自动挑选 BGM 的规则
- 多种宣传片视觉模板
