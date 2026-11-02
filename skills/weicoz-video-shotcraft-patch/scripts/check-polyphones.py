#!/usr/bin/env python3
"""检查配音稿里的多音字：按语境规则标出读音，把 TTS 容易读错的写法和没有规则覆盖的多音字列出来人工核对。

用法：check-polyphones.py <工程目录> [--src vo/script] [-v]
读：<src>/segNN.txt（配音稿，已是中文数字）；<工程>/vo/pronounce.json 若存在，说明哪些词已做了读音处理。
输出：
  高风险：TTS 常读错的词（间推、能当、还给…），附建议写法。默认读错概率高，必须处理或试听确认。
  需核对：命中多音字、但没有规则确认读音的位置，看语境判断，拿不准就试听。
  -v 另外列出规则已确认读音的位置。
退出码：有「高风险」未处理时为 1。

处理办法（二选一，优先第一个）：
  1. 改稿：换成没有歧义的说法，字幕稿和配音稿一起改。
  2. 在 vo/pronounce.json 写 {"字幕里的词": "配音里的词"}（如 {"间推": "间接推"}），zh-numerals.py 生成配音稿时替换，字幕不受影响。
  同音字替换（如 差价→插价）只在前两种都不行时用，换完必须试听。
"""
import argparse
import json
import re
import sys
from pathlib import Path

# 高风险：(模式, 正确读音, 建议)
RISKY = [
    (r"间推", "jiàn（间接）", "在 vo/pronounce.json 写 {\"间推\": \"间接推\"}"),
    (r"能当\s*[一二三四五六七八九十两\d]", "dàng（当作）", "写成「能抵」「相当于」"),
    (r"不值当", "dàng", "读 dàng，核对"),
    (r"(?<!不)得回来|得去|得先|得有|得用", "děi", "改成「要」「必须」，避免读成 dé"),
    (r"着急|睡着|着火|着手|着陆", "zháo/zhuó", "核对读音"),
    (r"会计|财会", "kuài", "「会」读 kuài，核对"),
    (r"重复|重新|重来", "chóng", "核对；「重要/重量」读 zhòng"),
    (r"调整|调度", "tiáo/diào", "核对"),
]

# 规则：(多音字, 语境模式, 读音)；命中即视为已确认
RULES = [
    ("还", r"还(?=给|你|款)|归还|偿还", "huán"),
    ("还", r"还(?=多|有|是|不|没|在|能|会|要|可|得|很|更|比|只|差|敢|早|剩|算|真|这|那)", "hái"),
    ("行", r"(?:银|同|一|行业)行|行业", "háng"),
    ("行", r"进行|运行|行动|不行|可行|旅行|发行", "xíng"),
    ("差", r"差(?=价|额|距|别|异)", "chā"),
    ("差", r"差不多|差点|差一点|相差|级差|落差|时差|价差", "chà/chā"),
    ("重", r"重(?=要|量|点|大|心|视)|[一-鿿]层比一层重|比[一-鿿]*重", "zhòng"),
    ("重", r"重(?=复|新|来|叠|启|建)", "chóng"),
    ("长", r"长(?=期|远|久|度|线)", "cháng"),
    ("长", r"成长|家长|长大|店长", "zhǎng"),
    ("调", r"调(?=整|度|节|动|配|查)", "tiáo/diào"),
    ("都", r"都(?=是|要|有|能|会|在|算|不|没|得|可|从|由|给|被|付|带)|都[,，]", "dōu"),
    ("间", r"中间|时间|空间|房间|之间|期间|每间|这间|间接", "jiān/jiàn"),
    ("为", r"为(?=什么|了|啥|何)|因为|所为", "wèi"),
    ("为", r"为止|为准|为主|为例|为难|成为|作为", "wéi"),
    ("为", r"成为|作为|认为|以为|行为|视为|称为|叫作为", "wéi"),
    ("得", r"[一-鿿]得(?=多|少|快|慢|好|大|小|远|近|高|低|清|明白|很|够|起|动|越|狠|勤)|拿得|赚得|算得|分得|划得|带得|滚得|进得", "de"),
    ("得", r"得到|获得|取得|值得|不得|觉得", "dé/de"),
    ("得", r"得(?=回|去|先|有|用|靠|做)", "děi"),
    ("着", r"[一-鿿]着(?=不|用|看|说|听|走|等|跑|送|你|他|它)|带着|拿着|跟着|接着|放着", "zhe"),
    ("数", r"数(?=字|据|量|目|额|学|值)", "shù"),
    ("数", r"数(?=一数|着|钱|清)", "shǔ"),
    ("当", r"当(?=然|时|天|初|前|地|心|年|成|作)|相当|应当|担当", "dāng"),
    ("当", r"值当|恰当|得当|妥当|上当|当铺", "dàng"),
    ("种", r"[一二三四五六七八九十两几各这那每]种|种类|品种", "zhǒng"),
    ("分", r"分(?=成|走|给|开|次|摊|配|钱|享|拆|批|区|账|拿|层|享)|占分|划分|拆分", "fēn"),
    ("分", r"成分|情分|本分|缘分|福分", "fèn"),
    ("少", r"少(?=拿|赚|花|给|一|点|许|数|量)|多少|减少|至少|缺少", "shǎo"),
    ("好", r"好(?=处|像|多|些|吃|看|用|玩|比|在)|很好|最好|更好|比较好|友好", "hǎo"),
    ("了", r"了(?=[，。！？；：、]|$)|[吃喝买拿回做看]了|好了|算了|有了|成了", "le"),
    ("了", r"了不起|了得|了结|了解|受不了|吃不了|干不了|不了", "liǎo"),
    ("便", r"顺便|方便|随便|便利|便捷|便于", "biàn"),
    ("便", r"便宜", "pián"),
    ("背", r"背后|背面|背景|背靠|后背", "bèi"),
    ("背", r"背包|背着|背债|背负", "bēi"),
    ("会", r"(?:不|一|将|还|也|就|才|都|只|能|可|应|一定)?会(?=有|是|做|被|变|让|涨|赚|亏|想|来|去|用|买|算|怎)", "huì"),
    ("处", r"好处|坏处|用处|益处|处处|各处|到处|相处", "chù/chǔ"),
    ("传", r"传(?=播|递|统|说|达|单|送)|推传|相传|转传", "chuán"),
    ("给", r"给(?=你|他|她|它|我|盟|服|用|平|客|大|人|区|省|市|钱|一)|送给|交给|还给|付给|拿给|分给|发给", "gěi"),
    ("担", r"担(?=心|保|任|当|忧|责)", "dān"),
    ("难", r"难(?=受|得|道|免|度|以|怪|看|听|题)|困难|为难", "nán"),
    ("倒", r"倒(?=是|贴|闭|退|过来)|倒下|打倒", "dǎo/dào"),
    ("转", r"转(?=账|化|换|发|成|变|身|手|让|向|入|出|给)|周转|运转|中转|流转", "zhuǎn"),
    ("参", r"参(?=与|加|考|数|照|差)", "cān"),
    ("觉", r"觉得|感觉|发觉|察觉|知觉|直觉|视觉|觉醒", "jué"),
    ("载", r"载(?=体|入|荷)|下载|上载|装载|刊载|记载|承载", "zài/zǎi"),
    ("乐", r"快乐|乐(?=意|趣|观|于)|欢乐", "lè"),
    ("假", r"假(?=如|设|装|的|话|冒|象)|真假", "jiǎ"),
    ("降", r"降(?=低|价|到|下|为)|下降|降(?=不)", "jiàng"),
    ("薄", r"薄(?=利|弱|膜|层|薄)", "bó/báo"),
    ("角", r"角(?=色|度|落|落|逐|形)|主角|配角|街角|三角", "jiǎo/jué"),
    ("切", r"一切|切(?=实|合|断|换|割|入|开|成|忌)|恳切|迫切|亲切", "qiè/qiē"),
    ("朝", r"朝(?=着|向|前|后|阳|代|廷)|王朝", "cháo/zhāo"),
    ("曾", r"曾(?=经|有|是|说|做|在)|未曾|不曾", "céng"),
    ("相", r"相(?=信|同|当|关|互|比|差|符|对|反|似|应|识|处|信)|互相|真相|相(?=亲)", "xiāng/xiàng"),
    ("率", r"率(?=先|领|直|真)|比率|概率|利率|费率|汇率|转化率|成功率|效率|频率", "shuài/lǜ"),
    ("率", r"[一-鿿]率", "lǜ"),
    ("率", r"率(?=先|领)", "shuài"),
    ("率", r"(?:比|概|利|费|汇|效|频|转化|成功|增长)率", "lǜ"),
]

# 只标这些字：绝大多数引擎读对「分、了、会、给、少、好、都」，逐个列出只会淹没真问题
POLY = set("行重长调间为得当数种差传担假降角切朝曾相率倒转参觉载乐薄处便背")


def sentences(text):
    return [x.strip() for x in re.split(r"(?<=[。！？\n])", text) if x.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--src", default="vo/script")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    root = Path(a.project)
    files = sorted((root / a.src).glob("seg*.txt"))
    if not files:
        print(f"错误：{root / a.src} 下没有 segNN.txt。")
        return 2
    pron = {}
    pp = root / "vo/pronounce.json"
    if pp.exists():
        pron = json.loads(pp.read_text(encoding="utf-8"))
    risky_hits, check, ok = [], [], []
    for f in files:
        text = f.read_text(encoding="utf-8")
        for si, sent in enumerate(sentences(text)):
            for pat, reading, tip in RISKY:
                for m in re.finditer(pat, sent):
                    risky_hits.append((f.stem, si, m.group(0), reading, tip, sent))
            for i, ch in enumerate(sent):
                if ch not in POLY:
                    continue
                ctx = sent[max(0, i - 4): i + 5]
                hit = None
                for c, pat, rd in RULES:
                    if c != ch:
                        continue
                    for m in re.finditer(pat, sent):
                        if m.start() <= i < m.end():
                            hit = rd
                            break
                    if hit:
                        break
                (ok if hit else check).append((f.stem, si, ch, ctx, hit))
    unhandled = 0
    print("== 高风险（TTS 常读错）==")
    for stem, si, word, reading, tip, sent in risky_hits:
        handled = any(k in sent or k == word for k in pron) and any(v for v in pron.values())
        mark = "已处理" if (word in pron or any(word in k for k in pron)) else "待处理"
        if mark == "待处理":
            unhandled += 1
        print(f"  [{mark}] {stem} 第 {si} 句「{word}」读 {reading}：{tip}\n         {sent}")
    if not risky_hits:
        print("  无")
    print("\n== 需核对（多音字无规则确认）==")
    for stem, si, ch, ctx, _ in check:
        print(f"  {stem} 第 {si} 句「{ch}」…{ctx}…")
    if not check:
        print("  无")
    if a.verbose:
        print("\n== 规则已确认 ==")
        for stem, si, ch, ctx, rd in ok:
            print(f"  {stem} 第 {si} 句「{ch}」→ {rd}  …{ctx}…")
    print(f"\n高风险 {len(risky_hits)}（待处理 {unhandled}），需核对 {len(check)}，已确认 {len(ok)}")
    return 1 if unhandled else 0


if __name__ == "__main__":
    sys.exit(main())
