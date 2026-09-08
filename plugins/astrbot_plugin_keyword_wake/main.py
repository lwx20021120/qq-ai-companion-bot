# -*- coding: utf-8 -*-
"""群聊唤醒插件 v2：关键词唤醒 + 图片消息唤醒

1. 关键词唤醒：消息包含关键词（小织/小织织/织织）→ 100% 必回
2. 图片唤醒：群里有人发图片 → 按概率唤醒，让机器人像真人一样
   "看到"图片并可能插话吐槽（图片会由视觉模型自动转述后传给主模型）

未唤醒的图片仍会被群聊上下文记录（含转述文字），她下次说话时也能"记得"。
"""

import random

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Image
from astrbot.api.star import Context, Star
from astrbot.core.platform.message_type import MessageType
from astrbot.core.star.filter.custom_filter import CustomFilter

# 触发关键词列表：消息中出现任意一个即唤醒（按需增删）
KEYWORDS = ["小织", "小织织", "织织"]

# 图片唤醒概率：群友发图时她"注意到"并可能插话的概率
# 1.0 = 每张图都会看并反应；0.5 = 一半概率；太吵可调低
IMAGE_WAKE_PROBABILITY = 0.5


class KeywordWakeFilter(CustomFilter):
    def filter(self, event: AstrMessageEvent, cfg) -> bool:
        # 仅群聊生效（私聊本来就是必回的）
        if event.get_message_type() != MessageType.GROUP_MESSAGE:
            return False
        # 已被 @ 或唤醒前缀唤醒的消息交给默认流程，避免重复回复
        if event.is_at_or_wake_command:
            return False

        text = event.message_str or ""
        # 1) 文字含关键词 → 必唤醒
        if any(kw in text for kw in KEYWORDS):
            return True

        # 2) 消息带图片 → 按概率唤醒（像真人瞥见图偶尔吐槽）
        if IMAGE_WAKE_PROBABILITY > 0:
            for comp in event.get_messages():
                if isinstance(comp, Image):
                    return random.random() < IMAGE_WAKE_PROBABILITY

        return False


class KeywordWakePlugin(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)

    @filter.custom_filter(KeywordWakeFilter, raise_error=False, priority=1000)
    async def keyword_wake(self, event: AstrMessageEvent) -> None:
        """含关键词或带图片的群消息 → 标记为唤醒，走标准 LLM 回复流程"""
        event.is_wake = True
        event.is_at_or_wake_command = True
