# QQ AI 陪伴机器人部署方案（AstrBot + NapCat + DeepSeek）

一套完整的 QQ 群 AI 陪伴机器人部署方案：傲娇人设 + 多模态识图 + 关键词唤醒 + 主动插话 + 表情包反击 + 链接解析 + 点歌，跑在云服务器上 24 小时在线。

## 效果预览

机器人在群里的日常：
- 群友提她名字（无需@）→ 100% 接话，傲娇语气
- 群友发表情包 → 她能"看到"图并吐槽（多模态），50% 概率插话
- 普通闲聊 → 低概率主动插嘴，像真人群友
- 发 B站/抖音/小红书链接 → 自动解析出视频/图集
- "小织来首歌" → 点歌卡片播放
- 越聊越懂你们群的黑话（自主学习）
- 聊天记录持久化，重启不丢记忆，能接上几天前的话题

## 架构

```
QQ（机器人号）
   ↕ NapCat 容器（OneBot v11 协议端，扫码登录）
   ↕ 反向 WebSocket
   ↕ AstrBot 容器（消息处理中枢）
      ├── DeepSeek API（主脑，原生多模态模型，能直接看图）
      ├── 关键词唤醒插件（自定义）
      └── 表情包管理/自主学习/主动消息/链接解析/点歌 等插件
```

## 快速部署

### 1. 准备

- 一台云服务器（2核2G 起步；学生可用阿里云「云工开物」300 元券 0 元购）
- 一个 DeepSeek API Key（platform.deepseek.com）
- 一个用作机器人的 QQ 小号

### 2. 启动

```bash
mkdir -p bot && cd bot
# 下载本仓库的 docker-compose.yml（先填入你的机器人QQ号）
docker compose up -d
```

### 3. 配置

1. 访问 `http://服务器IP:6099`（NapCat WebUI），扫码登录机器人 QQ
2. NapCat 网络配置 → 新建 WebSocket 客户端 → URL 填 `ws://astrbot:6199/ws`
3. 访问 `http://服务器IP:6185`（AstrBot WebUI，初始密码看容器日志）
4. 模型提供商 → 新增 DeepSeek（填 API Key，模型选 `deepseek-v4-flash-vision-exp`，原生多模态可直接看图）
5. 人格设定 → 导入 `persona/` 下的人设文件（把 `<主人QQ号>` 换成你自己的号）
6. 安装插件：把 `plugins/` 下的目录复制到 AstrBot 的 `data/plugins/`，或在插件市场搜索安装

### 4. 推荐插件（插件市场均可搜到）

| 插件 | 作用 |
|---|---|
| astrbot_plugin_keyword_wake（本仓库） | 关键词/图片消息唤醒，无需 @ |
| astrbot_plugin_meme_manager | 自动收集表情包 + 按情绪发表情包 |
| astrbot_plugin_self_learning | 自主学习群聊风格与黑话 |
| astrbot_plugin_proactive_chat | 智能主动消息（动态情绪/免打扰） |
| astrbot_plugin_parser | B站/抖音/小红书等链接自动解析 |
| astrbot_plugin_music | 点歌 |

## 踩坑记录（重要）

1. **跨容器发文件失败**：插件下载的媒体文件在 astrbot 容器里，NapCat 读不到。解法见 compose 里的共享挂载注释（`plugin_data` 以相同路径挂进两个容器）
2. **图片"看不了"**：给纯文本模型配视觉模型时，主模型的 `modalities` 若为空列表会被当作"支持所有模态"导致转述管道被跳过；直接把主模型换成原生多模态模型最省心
3. **国内服务器**：Docker 镜像加速、GitHub 克隆走镜像（如 ghfast.top）、插件依赖 pip 走国内源
4. **重登**：改 compose 重建 napcat 容器后 QQ 需重新扫码；登录数据都在挂载卷里，日常重启不受影响

## 关键词唤醒插件说明

`plugins/astrbot_plugin_keyword_wake`：群消息包含关键词（默认"小织/小织织/织织"）时 100% 唤醒回复；含图片的消息按概率唤醒（默认 50%，代码里可调）。

## 声明

本项目基于开源项目 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 与 [NapCat](https://github.com/NapNeko/NapCatQQ) 部署整合，仅供学习交流。请遵守相关平台条款使用，机器人账号有被风控的风险，请自行评估。
