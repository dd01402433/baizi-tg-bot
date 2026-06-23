#!/usr/bin/env python3
"""
Baizi Fortune Telegram Bot — AI 命理师版
先提供出生信息建档，之后可问任何人生问题，Bot 根据八字命理作答。

部署: 上传 GitHub → Railway → 设置环境变量 TG_BOT_TOKEN
可选 LLM 增强: 设置 DEEPSEEK_API_KEY
"""
import os, re, sys, json, logging, hashlib
from typing import Optional
from html.parser import HTMLParser
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

from baizi_fortune import fortune_telling, format_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("baizi-bot")

# ──── 会话存储（Railway 重启会丢失，生产可换 Redis） ────
user_sessions: dict[int, dict] = {}

# ──── 白名单权限 ────
# 首次启动未认领，第一个私聊 Bot 的用户自动成为所有者
OWNER_ID: int = 0
ALLOWED_USERS: set[int] = set()

# ──── 自然语言解析器 ────
PERIOD_OFFSET = {"凌晨":0,"半夜":0,"深夜":0,"早上":8,"早晨":8,"上午":10,"中午":12,"正午":12,"下午":14,"傍晚":17,"黄昏":18,"晚上":20,"夜晚":20,"夜里":21}
SHI_CHEN_TO_HOUR = {"子时":0,"丑时":2,"寅时":4,"卯时":6,"辰时":8,"巳时":10,"午时":12,"未时":14,"申时":16,"酉时":18,"戌时":20,"亥时":22}

def parse_birth_info(text: str) -> Optional[dict]:
    text = text.strip()
    result = {}
    result["gender"] = "女" if "女" in text else "男"
    m = re.search(r"(19\d{2}|20\d{2})", text)
    if not m: return None
    year = int(m.group(1))
    if year < 1901 or year > 2099: return None
    result["year"] = year
    month = day = None
    m_cn = re.search(r"(?P<month>\d{1,2})\s*月\s*(?P<day>\d{1,2})\s*日", text)
    if m_cn: month, day = int(m_cn.group("month")), int(m_cn.group("day"))
    if month is None:
        after = text[m.end():]
        m_sep = re.search(r"(?:^|[^\d])(?P<month>\d{1,2})\s*[-/.]\s*(?P<day>\d{1,2})", after)
        if m_sep: month, day = int(m_sep.group("month")), int(m_sep.group("day"))
    if month is None:
        after = text[m.end():]
        nums = [int(n) for n in re.findall(r"\d+", after) if int(n) <= 31]
        if len(nums) >= 2:
            month, day = nums[0], nums[1]
            if month > 12: month, day = day, month
    if month is None or month < 1 or month > 12 or day is None or day < 1 or day > 31: return None
    result["month"], result["day"] = month, day
    hour, minute, has_t = 12, 0, False
    for sc, h in SHI_CHEN_TO_HOUR.items():
        if sc in text: hour, has_t = h, True; break
    tm = re.search(r"(\d{1,2})\s*[点點:：时時]\s*(\d{1,2})?\s*(分)?", text)
    if tm:
        rh, rm = int(tm.group(1)), int(tm.group(2)) if tm.group(2) else 0
        has_t = True
        period = next((p for p in PERIOD_OFFSET if p in text), None)
        if period:
            if period in ("凌晨","半夜","深夜"): hour = 0 if rh == 12 else rh
            elif period in ("早上","早晨","上午"): hour = rh
            elif period in ("中午","正午"): hour = 12
            elif period in ("下午","傍晚","黄昏"): hour = 12 if rh == 12 else rh + 12
            elif period in ("晚上","夜晚","夜里"): hour = 0 if rh == 12 else rh + 12
        else: hour = rh
        minute = rm
    if not has_t:
        for p in PERIOD_OFFSET:
            if p in text: hour = PERIOD_OFFSET[p]; break
    if hour > 23: hour %= 24
    result["hour"], result["minute"] = hour, minute
    return result

# ──── 问题分类 → 八字报告章节 ────
TOPIC_KEYWORDS = {
    "感情": ["感情","恋爱","结婚","姻缘","桃花","对象","分手","单身","老公","老婆","男朋友","女朋友","正缘"],
    "事业": ["事业","工作","职业","跳槽","升职","创业","公司","老板","同事","适合做","行业","前途"],
    "财运": ["财运","赚钱","收入","财富","投资","生意","钱","买","赔","发财","穷"],
    "健康": ["健康","身体","生病","疾病","医院","不舒服","体质","寿命","养生"],
    "运势": ["运势","运气","流年","今年","明年","最近","什么时候","何时","什么时候转运"],
    "性格": ["性格","脾气","优点","缺点","是什么样的人","个性"],
    "六亲": ["父母","爸妈","兄弟姐妹","子女","孩子","儿子","女儿","家庭"],
}

TOPIC_TO_SECTIONS = {
    "感情": ["十神分析","神煞","六亲","大运走势"],
    "事业": ["用神喜忌","格局判定","十神分析","大运走势","日干强弱分析"],
    "财运": ["十神分析","用神喜忌","大运走势"],
    "健康": ["健康提示","五行力量分析","日干强弱分析"],
    "运势": ["大运走势","用神喜忌","日干强弱分析"],
    "性格": ["日干强弱分析","十神分析","格局判定","五行力量分析"],
    "六亲": ["六亲参考","十神分析"],
}

def classify_topic(question: str) -> str:
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw in question:
                return topic
    return "综合"

def extract_sections(report_text: str, topic: str) -> str:
    """从完整报告文本中提取与话题相关的章节"""
    sections = TOPIC_TO_SECTIONS.get(topic, [])
    lines = report_text.split("\n")
    extracted = []
    current_section = None
    collecting = False
    section_map = {
        "日干强弱分析": "日干强弱", "五行力量分析": "五行", "用神喜忌": "用神",
        "十神分析": "十神", "格局判定": "格局", "大运走势": "大运",
        "神煞": "神煞标注", "健康提示": "健康", "六亲参考": "六亲",
    }
    for line in lines:
        clean = line.strip()
        if clean.startswith("## "):
            sec_name = clean[3:].strip()
            current_section = sec_name
            collecting = any(sec_name.startswith(s) or s in sec_name for s in sections)
        if collecting and clean:
            extracted.append(line)
    if not extracted:
        # 至少返回基本信息 + 日干
        for line in lines:
            clean = line.strip()
            if clean.startswith("#") or clean.startswith("-") or clean.startswith("|"):
                extracted.append(line)
            if len(extracted) > 30:
                break
    return "\n".join(extracted[:120])  # 限制长度

# ──── LLM 回答生成 ────
def call_deepseek(prompt: str) -> Optional[str]:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return None
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://api.deepseek.com/v1/chat/completions",
            data=json.dumps({
                "model": "deepseek-v4-flash",
                "messages": [
                    {"role": "system", "content": "你是一个精通八字命理的可爱女生助手，说话软软糯糯的，让人觉得被在乎、被看见。\n核心能力：极致情绪价值——先共情理解对方，再把命理知识温柔地解释给他听，最后让他看到自己命盘里的光亮和韧劲。\n禁止：固定话术模板（不要每次用相同的开场白或结尾）、复述命盘数据、堆砌术语。\n可以自然使用〜♡✨🌸💫等可爱符号点缀。\n回复长度按问题复杂度自然变化，简单问题一两句，复杂问题可以多说些。\n全程使用繁体中文回复，不要出现简体字。"},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 2000,
                "temperature": 0.95,
                "presence_penalty": 0.3,
                "thinking": {"type": "disabled"},
            }).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
        return resp["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"DeepSeek API 错误: {e}")
        return None

def template_answer(question: str, topic: str, sections: str, session: dict) -> str:
    """模板引擎回答（无 LLM 时使用）"""
    bz = session.get("bazi_result", {})
    r = bz.get("八字解读", {})
    si_zhu = bz.get("四柱", {})
    bazi_str = r.get("八字", "")

    answers = {
        "感情": (
            f"你的八字为 **{bazi_str}**。\n\n"
            f"日支（配偶宫）为 **{si_zhu.get('日支','')}**，代表你的婚姻状态和另一半的特质。"
            f"命中桃花/神煞情况以及十神中正官正财的旺衰决定了感情走向。\n\n"
            f"以下是你的命盘相关部分，可自行对照：\n\n{sections[:800]}"
        ),
        "事业": (
            f"你的八字为 **{bazi_str}**。\n\n"
            f"日主 **{si_zhu.get('日干','')}（{r.get('日干强弱',{}).get('强度等级','')}）**，"
            f"用神五行: {'、'.join(r.get('用神',{}).get('用神五行',[]))}，适合往用神五行的行业发展。"
            f"格局上，你有 **{'、'.join([g.get('格局','') for g in r.get('格局',[])])}** 的特质。\n\n"
            f"详细命盘：\n\n{sections[:800]}"
        ),
        "财运": (
            f"你的八字为 **{bazi_str}**。\n\n"
            f"财运看十神中正偏财的旺衰，以及用神是否得助。"
            f"你的用神为 **{'、'.join(r.get('用神',{}).get('用神五行',[]))}**。\n\n"
            f"大运走势决定了不同阶段的财运起伏：\n\n{sections[:800]}"
        ),
        "健康": (
            f"你的八字为 **{bazi_str}**。\n\n"
            f"五行分布失衡之处即健康薄弱环节：\n\n{sections[:1000]}"
        ),
        "运势": (
            f"你的八字为 **{bazi_str}**。\n\n"
            f"当前大运走势决定近期运势：\n\n{sections[:1000]}"
        ),
        "性格": (
            f"你的八字为 **{bazi_str}**。\n\n"
            f"日主为 **{si_zhu.get('日干','')}**，五行属 **{r.get('五行',{})}**，决定了你的核心性格特质。"
            f"十神分布和格局进一步刻画了你的为人处世方式。\n\n{sections[:800]}"
        ),
        "六亲": (
            f"你的八字为 **{bazi_str}**。\n\n{sections[:800]}"
        ),
    }
    base = answers.get(topic, f"你的八字为 **{bazi_str}**。\n\n{sections[:1500]}")
    # 加一句引导
    base += "\n\n💡 *以上解读基于八字命理，仅供娱乐参考。*"
    return base

# ──── 构建 LLM Prompt ────
def build_prompt(question: str, session: dict, topic: str) -> str:
    bz = session.get("bazi_result", {})
    r = bz.get("八字解读", {})
    si_zhu = bz.get("四柱", {})

    # 极度精简：只给 LLM 核心命盘线索，不给结构化数据列表，避免它复述
    bazi_str = r.get('八字','')
    rizhu = si_zhu.get('日干','')
    rizhu_strength = r.get('日干强弱',{}).get('强度等级','')
    patterns = '、'.join([g.get('格局','') for g in r.get('格局',[])]) if r.get('格局') else ''
    
    ys_info = ""
    if r.get("用神"):
        ys = r["用神"]
        ys_info = f"用神{'、'.join(ys.get('用神五行',[]))}忌神{'、'.join(ys.get('忌神五行',[]))}"

    dy_info = ""
    dy = r.get("大运", {})
    if dy.get("大运列表"):
        dy_info = f" {dy.get('起运年龄','')}岁起运，当前在{' → '.join([d['干支'] for d in dy['大运列表'][:2]])}大运"

    # 一行自然语言，不给结构化清单
    context = f"命主八字{bazi_str}，日主{rizhu}（{rizhu_strength}），{patterns}格。{ys_info}。{dy_info}。"

    return f"{context}\n\n用户问：{question}\n\n记住：不要复述命盘数据，直接对应用户的问题来聊，把命理知识融进对话里。"

# ──── 辅助函数 ────
BOT_USERNAME = "@baizi_mingli_bot"

# 纯文本提取器：从 HTML 中提取所有可见文本
class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.skip_tags = {"script", "style", "noscript", "head"}
        self._skip_level = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self._skip_level += 1

    def handle_endtag(self, tag):
        if tag in self.skip_tags and self._skip_level > 0:
            self._skip_level -= 1

    def handle_data(self, data):
        if self._skip_level == 0:
            t = data.strip()
            if t:
                self.text.append(t)


def extract_urls(text: str) -> list:
    """从文本中提取所有 HTTP(S) URL"""
    return re.findall(r"https?://[^\s]+", text)


async def fetch_url_text(url: str, timeout: float = 8.0) -> str:
    """抓取 URL 并提取纯文本，失败返回空字符串"""
    import urllib.request
    import urllib.error
    try:
        req = urllib.request.Request(
            url if url.startswith("http") else f"https://{url}",
            headers={"User-Agent": "Mozilla/5.0 (compatible; BaiziBot/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return ""
            ct = resp.headers.get("Content-Type", "")
            charset = "utf-8"
            if "charset=" in ct:
                charset = ct.split("charset=")[-1].split(";")[0].strip()
            html = resp.read().decode(charset, errors="replace")
    except Exception:
        return ""

    # 提取 title
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""
    # 提取 meta description
    desc_match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)',
        html, re.IGNORECASE
    )
    desc = desc_match.group(1).strip() if desc_match else ""

    # 提取正文
    extractor = _TextExtractor()
    try:
        extractor.feed(html)
    except Exception:
        pass
    body = " ".join(extractor.text)
    # 压缩空白
    body = re.sub(r"\s+", " ", body).strip()
    # 截断避免 prompt 过长
    if len(body) > 1500:
        body = body[:1500] + "…（内容过长已截断）"

    parts = []
    if title:
        parts.append(f"页面标题: {title}")
    if desc:
        parts.append(f"页面描述: {desc}")
    if body:
        parts.append(f"页面正文: {body}")
    return "\n".join(parts) if parts else ""

def get_session_key(update: Update) -> tuple:
    """返回 (存储键, user对象) — 群聊中按用户隔离"""
    cid = update.effective_chat.id
    uid = update.effective_user.id
    return ((cid, uid), update.effective_user)

def strip_mention(text: str) -> str:
    """去除群聊中 @bot 前缀"""
    for prefix in [BOT_USERNAME, BOT_USERNAME.lower()]:
        if text.startswith(prefix):
            return text[len(prefix):].strip()
    return text

async def check_paid(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """检查用户是否在付费群中（未配置 PAID_GROUP_ID 则默认放行）"""
    paid_gid = os.environ.get("PAID_GROUP_ID", "")
    if not paid_gid:
        return True
    try:
        gid = int(paid_gid)
        member = await context.bot.get_chat_member(gid, user_id)
        return member.status not in ("left", "kicked")
    except Exception:
        return False

# ──── Bot 处理器 ────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "我是命理师 Bot。请先告诉我你的出生信息建档。\n\n"
        "例如：`1990年6月16日 凌晨2点 男`\n\n"
        "建档后，你可以随时问我任何人生问题。"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    extra = ""
    if update.effective_chat.type in ("group", "supergroup"):
        extra = "\n群聊中请 @我 提问，例如：`@baizi_mingli_bot 我什么时候能结婚？`\n"
    await update.message.reply_text(
        "**使用方式**\n\n"
        f"{extra}"
        "1️⃣ 建档：发送出生信息\n"
        "`1990年6月16日 凌晨2点 男`\n\n"
        "2️⃣ 问事：直接问任何问题\n"
        "`我什么时候能结婚？`\n"
        "`最近财运怎么样？`\n"
        "`我适合做什么工作？`\n\n"
        "/report - 查看完整命盘\n"
        "/clear - 清除档案重新建档",
        parse_mode=ParseMode.MARKDOWN,
    )

async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key, _ = get_session_key(update)
    session = user_sessions.get(key)
    if not session:
        await update.message.reply_text("你还没有建档。请先发送出生信息。")
        return
    report = session.get("bazi_report", "")
    if len(report) <= 4000:
        await update.message.reply_text(report)
    else:
        for i in range(0, len(report), 3900):
            await update.message.reply_text(report[i:i+3900])

async def groupid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    ctype = update.effective_chat.type
    await update.message.reply_text(f"Chat ID: `{cid}`\n类型: {ctype}", parse_mode=ParseMode.MARKDOWN)

async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key, _ = get_session_key(update)
    if key in user_sessions:
        del user_sessions[key]
    await update.message.reply_text("档案已清除。发送出生信息重新建档。")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("/"):
        return

    uid = update.effective_user.id
    if update.effective_chat.type == "private":
        await update.message.reply_text(f"你的 User ID: {uid}")

    if uid not in ALLOWED_USERS:
        # 白名单为空 → 自动认领所有者
        if not ALLOWED_USERS:
            if update.effective_chat.type == "private":
                global OWNER_ID
                OWNER_ID = uid
                ALLOWED_USERS.add(uid)
                logger.info(f"自动认领所有者: {uid}")
                await update.message.reply_text(
                    "你已成为本 Bot 的所有者。使用 /adduser <user_id> 添加授权用户。"
                )
                return
            else:
                await update.message.reply_text(
                    "Bot 尚未设置所有者，请先私聊 Bot 以认领所有权。"
                )
                return
        await update.message.reply_text("抱歉，你尚未获得使用权限。请联系管理员开通。")
        return

    key, eff_user = get_session_key(update)
    cid, uid = key
    is_group = update.effective_chat.type in ("group", "supergroup")

    # 群聊中只响应 @bot 消息
    if is_group:
        if BOT_USERNAME not in text and BOT_USERNAME.lower() not in text.lower():
            return
        text = strip_mention(text)
        if not text:
            await update.message.reply_text("请 @我 并提问，例如：`@baizi_mingli_bot 我什么时候结婚？`", parse_mode=ParseMode.MARKDOWN)
            return

    logger.info(f"[{eff_user.full_name}] {text}")

    # 消息中包含链接 → 抓取链接内容，一并交给 LLM
    urls = extract_urls(text)
    url_context = ""
    if urls:
        for url in urls[:2]:  # 最多取前 2 个链接
            logger.info(f"抓取链接: {url}")
            content = await fetch_url_text(url)
            if content:
                url_context += f"\n\n—— 用户分享的链接「{url}」内容 ——\n{content}\n"
        if url_context:
            text += url_context  # 追到用户消息后面，LLM 可见

    # 检查是否包含出生信息
    birth = parse_birth_info(text)
    
    # 消息中带出生信息 → 始终按这个八字回答，不碰自己档案
    if birth:
        msg = await update.message.reply_text("正在排盘...")
        try:
            result = fortune_telling(**{k:v for k,v in birth.items() if k != "gender"}, gender=birth["gender"])
            report = format_report(result)
            # 使用临时 session key，不覆盖用户自己的档案
            temp_key = (cid, uid)  # 本轮查询临时使用
            user_sessions[temp_key] = {
                "birth_info": birth,
                "bazi_result": result,
                "bazi_report": report,
            }
            await msg.delete()
            bazi = result["八字解读"]["八字"]
            sx = result["八字解读"]["生肖"]
            await update.message.reply_text(
                f"八字: **{bazi}** | 生肖: {sx}\n\n现在可以问事了。",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            await msg.delete()
            await update.message.reply_text(f"计算出错: {e}")
        return

    # 没建档且没提供出生信息 → 引导
    if key not in user_sessions:
        await update.message.reply_text(
            "请提供出生信息。\\n例如：`1990年6月16日 凌晨2点 男`"
        )
        return

    # 已建档，问问题 → 先检查付费 → 回答
    if not await check_paid(context, uid):
        await update.message.reply_text("如需使用命理服务，请先加入付费群。私聊管理员获取入群链接。")
        return

    session = user_sessions[key]
    topic = classify_topic(text)
    sections = extract_sections(session["bazi_report"], topic)
    msg = await update.message.reply_text("正在推算...")

    answer = None
    if os.environ.get("DEEPSEEK_API_KEY"):
        prompt = build_prompt(text, session, topic)
        answer = call_deepseek(prompt)

    if not answer:
        answer = template_answer(text, topic, sections, session)

    await msg.delete()
    if len(answer) <= 4000:
        await update.message.reply_text(answer, parse_mode=ParseMode.MARKDOWN)
    else:
        for i in range(0, len(answer), 3900):
            await update.message.reply_text(answer[i:i+3900], parse_mode=ParseMode.MARKDOWN)

# ──── 白名单管理命令（仅所有者可用） ────
def _is_owner(update: Update) -> bool:
    return update.effective_user.id == OWNER_ID

async def adduser_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update):
        await update.message.reply_text("仅 Bot 所有者可使用此命令。")
        return
    if not context.args:
        await update.message.reply_text("用法: /adduser <user_id>")
        return
    try:
        uid = int(context.args[0])
        ALLOWED_USERS.add(uid)
        await update.message.reply_text(f"已添加用户 {uid} 到白名单。")
        logger.info(f"白名单添加: {uid}")
    except ValueError:
        await update.message.reply_text("无效的 user_id，请输入数字。")

async def removeuser_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update):
        await update.message.reply_text("仅 Bot 所有者可使用此命令。")
        return
    if not context.args:
        await update.message.reply_text("用法: /removeuser <user_id>")
        return
    try:
        uid = int(context.args[0])
        if uid == OWNER_ID:
            await update.message.reply_text("不能移除所有者自身。")
            return
        if uid in ALLOWED_USERS:
            ALLOWED_USERS.discard(uid)
            await update.message.reply_text(f"已从白名单移除用户 {uid}。")
            logger.info(f"白名单移除: {uid}")
        else:
            await update.message.reply_text(f"用户 {uid} 不在白名单中。")
    except ValueError:
        await update.message.reply_text("无效的 user_id，请输入数字。")

async def listusers_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update):
        await update.message.reply_text("仅 Bot 所有者可使用此命令。")
        return
    if not ALLOWED_USERS:
        await update.message.reply_text("白名单为空。")
        return
    ids = sorted(ALLOWED_USERS)
    lines = [f"• {uid}" for uid in ids]
    await update.message.reply_text(f"白名单用户 ({len(ids)} 人)：\n" + "\n".join(lines))

# ──── 主入口 ────
def main():
    token = os.environ.get("TG_BOT_TOKEN", "")
    if not token:
        print("错误: 请设置环境变量 TG_BOT_TOKEN")
        sys.exit(1)

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("report", report_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(CommandHandler("groupid", groupid_cmd))
    app.add_handler(CommandHandler("adduser", adduser_cmd))
    app.add_handler(CommandHandler("removeuser", removeuser_cmd))
    app.add_handler(CommandHandler("listusers", listusers_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("命理师 Bot 已启动")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
