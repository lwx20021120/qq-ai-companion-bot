# -*- coding: utf-8 -*-
"""群功能增强插件：定时问候 / 群聊日报 / 欢迎新人 / 趣味互动

功能:
1. 每天早上 8:00 群内早安问候
2. 每天晚上 22:30 群内晚安问候
3. 每天晚上 23:00 群聊日报（当日消息统计）
4. 新成员入群自动欢迎（@新人）
5. 趣味互动命令: /抽签  /掷骰子  /塔罗

所有时间均为服务器本地时间。
"""

import asyncio
import datetime
import random
from collections import Counter, deque
from zoneinfo import ZoneInfo

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.event.filter import EventMessageType
from astrbot.api.message_components import At, Plain
from astrbot.api.star import Context, Star
from astrbot.core.message.message_event_result import MessageChain

# ====== 配置区 ======
GROUP_ID = "866530145"  # 目标群
GROUP_SESSION = f"aiocqhttp:GroupMessage:{GROUP_ID}"

MORNING = (8, 0)  # 早安时间 (时, 分)
NIGHT = (22, 30)  # 晚安时间
DAILY = (23, 0)  # 日报时间
MAX_DAILY_MSGS = 300  # 日报最多统计的消息条数
# ====================

MORNING_MSG = "早起的虫儿被鸟吃，早起的本小姐天下无敌！哼，新的一天都给本小姐打起精神来！(￣^￣)"
NIGHT_MSG = "夜深了，本小姐要下线了……才、才不是困了！你们也早点睡，熬夜会变丑的，笨蛋们。(｡•ˇ‸ˇ•｡)"

OMIKUJI = [
    ("大吉", "今日运势爆棚，本小姐都忍不住多看你两眼！"),
    ("中吉", "运气不错嘛，继续保持，别得意忘形！"),
    ("小吉", "还行还行，就是别太贪心哦。"),
    ("末吉", "平平淡淡的一天，正好适合摸鱼。"),
    ("凶", "倒霉蛋！今天少立 flag，出门小心点！"),
    ("大凶", "……要不你今天就窝在家里吧，本小姐勉强陪你。"),
]

TAROT = [
    ("愚者", "新的开始，勇敢往前冲，笨蛋也有春天！"),
    ("魔术师", "你有无限可能，别浪费天赋！"),
    ("女祭司", "跟着直觉走，别问为什么，信本小姐的！"),
    ("皇后", "丰盛的一天，吃吃喝喝美滋滋。"),
    ("皇帝", "掌控全场，今天你是主角！"),
    ("恋人", "有人惦记着你呢，别假装不知道。"),
    ("战车", "冲鸭！胜利就在前方！"),
    ("力量", "你比你以为的更强大，笨蛋！"),
    ("隐者", "独处思考一下吧，本小姐不打扰你。"),
    ("命运之轮", "运势在转动，好日子要来了。"),
    ("正义", "公平会降临，做对的事就好。"),
    ("倒吊人", "换个角度看问题，也许有惊喜。"),
    ("死神", "旧的不去新的不来，放手吧！"),
    ("节制", "张弛有度，别把自己逼太紧。"),
    ("恶魔", "诱惑当前，稳住，别上头！"),
    ("高塔", "突发变故？别慌，本小姐罩着你。"),
    ("星星", "希望就在前方，加油！"),
    ("月亮", "心里不安？那是正常的，明天会更好。"),
    ("太阳", "大晴天！好运连连！"),
    ("审判", "过去的努力要开花结果了。"),
    ("世界", "圆满！你想要的都会来！"),
]

# 日报统计时忽略的常见语气词（简单过滤）
STOP_WORDS = {"的", "了", "是", "我", "你", "他", "她", "它", "们", "在", "有", "就", "都",
              "啊", "吧", "吗", "呢", "哈", "呀", "哦", "嗯", "嘛", "这", "那", "不", "也",
              "和", "与", "个", "人", "说", "看", "去", "来", "到", "会", "能", "要", "让"}


class GroupFunPlugin(Star):
    def __init__(self, context: Context, config: dict | None = None) -> None:
        super().__init__(context, config)
        # (user_id, 昵称, 文本) 列表，用于日报统计
        self._daily_messages: deque[tuple[str, str, str]] = deque(maxlen=MAX_DAILY_MSGS)
        # 记录已触发过的日期（防止重复触发）
        self._morning_done: set[str] = set()
        self._night_done: set[str] = set()
        self._report_done: set[str] = set()

    async def initialize(self) -> None:
        """插件加载后启动后台定时任务"""
        asyncio.create_task(self._scheduler())
        self.logger.info("[群功能] 后台定时任务已启动")

    # ---------- 定时任务调度 ----------
    async def _scheduler(self) -> None:
        while True:
            try:
                # 统一使用北京时间，避免容器时区（UTC）导致定时错位
                now = datetime.datetime.now(ZoneInfo("Asia/Shanghai"))
                today = now.strftime("%Y-%m-%d")
                hm = (now.hour, now.minute)

                if hm == MORNING and today not in self._morning_done:
                    self._morning_done.add(today)
                    await self._send_group(MORNING_MSG)
                    self.logger.info("[群功能] 早安已发送")
                if hm == NIGHT and today not in self._night_done:
                    self._night_done.add(today)
                    await self._send_group(NIGHT_MSG)
                    self.logger.info("[群功能] 晚安已发送")
                if hm == DAILY and today not in self._report_done:
                    self._report_done.add(today)
                    await self._send_daily_report()
                    self.logger.info("[群功能] 日报已发送")
            except Exception as e:
                self.logger.error(f"[群功能] 定时任务异常: {e}")
            await asyncio.sleep(30)

    async def _send_group(self, text: str) -> None:
        try:
            await self.context.send_message(
                GROUP_SESSION, MessageChain([Plain(text)])
            )
        except Exception as e:
            self.logger.error(f"[群功能] 群消息发送失败: {e}")

    # ---------- 群聊日报 ----------
    async def _send_daily_report(self) -> None:
        msgs = list(self._daily_messages)
        self._daily_messages.clear()
        if not msgs:
            await self._send_group("今天群里安静得跟自习室似的，本小姐都找不到插嘴的机会！哼！(｡•ˇ‸ˇ•｡)")
            return

        total = len(msgs)
        # 活跃成员 top3
        sender_counter = Counter(m[0] for m in msgs)
        name_map = {m[0]: m[1] for m in reversed(msgs)}
        top_users = sender_counter.most_common(3)
        top_users_str = "、".join(
            f"{name_map.get(uid, uid)}({cnt}条)" for uid, cnt in top_users
        )
        # 高频词 top5（简单按字符切分，跳过语气词）
        word_counter = Counter()
        for _, _, text in msgs:
            for ch in text:
                if ch.strip() and ch not in STOP_WORDS:
                    word_counter[ch] += 1
        top_words = "、".join(w for w, _ in word_counter.most_common(5)) or "（无）"

        report = (
            f"【今日群聊日报】\n"
            f"共 {total} 条消息，够热闹的嘛！\n"
            f"🏆 最活跃: {top_users_str}\n"
            f"🔑 高频词: {top_words}\n"
            f"哼，本小姐今天可是都看在眼里了！(¬‿¬)"
        )
        await self._send_group(report)

    # ---------- 欢迎新人 ----------
    async def _welcome_new_member(self, event: AstrMessageEvent) -> None:
        user_id = event.get_sender_id()
        if not user_id:
            return
        welcome = (
            f"哦？来了个新面孔！本小姐先帮你占个座，以后跟本小姐混，懂？(￣▽￣)ノ"
        )
        try:
            await event.send(MessageChain([At(qq=user_id), Plain("\n" + welcome)]))
        except Exception as e:
            self.logger.error(f"[群功能] 欢迎消息发送失败: {e}")

    # ---------- 事件处理：群消息 + 新人入群 ----------
    @filter.event_message_type(EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent) -> None:
        raw = getattr(event.message_obj, "raw_message", None)
        # 群通知事件（新人入群）
        if isinstance(raw, dict):
            if raw.get("post_type") == "notice" and raw.get("notice_type") == "group_increase":
                await self._welcome_new_member(event)
                return
        # 普通群消息 → 收集用于日报
        if event.get_group_id() == GROUP_ID:
            text = (event.message_str or "").strip()
            if text and not text.startswith("/"):
                self._daily_messages.append(
                    (event.get_sender_id(), event.get_sender_name() or "群友", text)
                )

    # ---------- 趣味互动 ----------
    @filter.command("抽签")
    async def omikuji(self, event: AstrMessageEvent) -> None:
        level, comment = random.choice(OMIKUJI)
        event.plain_result(f"【今日抽签】{level}\n{comment}")

    @filter.command("掷骰子")
    async def roll_dice(self, event: AstrMessageEvent) -> None:
        n = random.randint(1, 6)
        event.plain_result(f"🎲 掷出了 {n} 点！" + (" 哇，手气不错嘛！" if n >= 5 else " 哼，一般般啦。"))

    @filter.command("塔罗")
    async def tarot(self, event: AstrMessageEvent) -> None:
        card, meaning = random.choice(TAROT)
        event.plain_result(f"🔮 你抽到了「{card}」\n{meaning}")
