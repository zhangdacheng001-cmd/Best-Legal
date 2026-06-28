#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch clean and anonymize locally downloaded public articles.

Typical use:
    python3 article_cleaner.py /path/to/articles
    python3 article_cleaner.py /path/to/articles --in-place
    python3 article_cleaner.py /path/to/articles --in-place --hard-delete

The script has no third-party dependency. It handles Markdown, TXT and simple
HTML files, adds YAML front matter, anonymizes subject information, and filters
obvious promotional articles by title keywords.
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import shutil
import sys
from collections import OrderedDict
from datetime import datetime
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path


DEFAULT_EXTENSIONS = (".md", ".markdown", ".txt", ".html", ".htm")
DEFAULT_PROMO_KEYWORDS = ("荣登", "祝贺", "邀请", "恭喜")
SCRIPT_NAME = "article_cleaner.py"

ROLE_PREFIXES = (
    "原告",
    "被告",
    "上诉人",
    "被上诉人",
    "申请人",
    "被申请人",
    "再审申请人",
    "再审被申请人",
    "第三人",
    "案外人",
    "债权人",
    "债务人",
    "买受人",
    "出卖人",
    "承包人",
    "发包人",
    "实际施工人",
    "用人单位",
    "劳动者",
    "赔偿请求人",
    "赔偿义务机关",
    "甲方",
    "乙方",
    "丙方",
    "丁方",
)

ORG_SUFFIXES = (
    "银行股份有限公司",
    "保险股份有限公司",
    "证券股份有限公司",
    "基金管理有限公司",
    "资产管理有限公司",
    "有限责任公司",
    "股份有限公司",
    "集团有限公司",
    "律师事务所",
    "会计师事务所",
    "合伙企业",
    "有限公司",
    "保险公司",
    "证券公司",
    "基金公司",
    "商贸公司",
    "担保公司",
    "银行",
    "公司",
)

PUBLIC_ORG_ALLOWLIST = {
    "最高人民法院",
    "人民法院报",
    "中华人民共和国最高人民法院",
}

GENERIC_ORG_TERMS = {
    "公司",
    "该公司",
    "本公司",
    "银行",
    "保险公司",
    "证券公司",
    "基金公司",
    "商贸公司",
    "担保公司",
    "律师事务所",
    "会计师事务所",
    "合伙企业",
}

PERSON_STOPWORDS = {
    "劳动者",
    "用人单位",
    "保险人",
    "投保人",
    "被保险人",
    "承运人",
    "发包人",
    "承包人",
    "买受人",
    "出卖人",
    "申请人",
    "被申请人",
    "上诉人",
    "被上诉人",
    "自然人",
    "负责人",
    "联系人",
    "法定代表人",
}

COMPOUND_SURNAMES = (
    "万俟",
    "司马",
    "上官",
    "欧阳",
    "夏侯",
    "诸葛",
    "闻人",
    "东方",
    "赫连",
    "皇甫",
    "尉迟",
    "公羊",
    "澹台",
    "公冶",
    "宗政",
    "濮阳",
    "淳于",
    "单于",
    "太叔",
    "申屠",
    "公孙",
    "仲孙",
    "轩辕",
    "令狐",
    "钟离",
    "宇文",
    "长孙",
    "慕容",
    "鲜于",
    "闾丘",
    "司徒",
    "司空",
    "亓官",
    "司寇",
    "仉督",
    "子车",
    "颛孙",
    "端木",
    "巫马",
    "公西",
    "漆雕",
    "乐正",
    "壤驷",
    "公良",
    "拓跋",
    "夹谷",
    "宰父",
    "谷梁",
    "段干",
    "百里",
    "东郭",
    "南门",
    "呼延",
    "归海",
    "羊舌",
    "微生",
    "梁丘",
    "左丘",
    "东门",
    "西门",
    "南宫",
)

SINGLE_SURNAMES = (
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
    "谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐"
    "费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟"
    "平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋庞熊纪舒屈项"
    "祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡"
    "田胡凌霍虞万支柯昝管卢莫经房裘缪干解应宗丁宣邓郁单杭洪包诸左"
    "石崔吉龚程邢裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫"
    "乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘斜厉戎祖武"
    "符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙"
    "池乔阴胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍却璩桑桂濮牛寿"
    "通边扈燕冀浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖"
    "庾终暨居衡步都耿满弘匡文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂"
    "晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺"
    "权逯盖益桓公岳帅缑亢况有琴商牟佘佴伯赏墨哈谯笪年爱阳佟"
)

PERSON_TOKEN_RE = re.compile(
    r"(?<![\u4e00-\u9fff])("
    + "|".join(map(re.escape, COMPOUND_SURNAMES))
    + r")[\u4e00-\u9fff]{1,2}(?![\u4e00-\u9fff])"
    + r"|(?<![\u4e00-\u9fff])(["
    + re.escape(SINGLE_SURNAMES)
    + r"])[\u4e00-\u9fff]{1,2}(?![\u4e00-\u9fff])"
)

SPACED_PERSON_TOKEN_RE = re.compile(
    r"(?<![\u4e00-\u9fff])("
    + "|".join(map(re.escape, COMPOUND_SURNAMES))
    + r")\s*[\u4e00-\u9fff](?:\s*[\u4e00-\u9fff])?(?![\u4e00-\u9fff])"
    + r"|(?<![\u4e00-\u9fff])(["
    + re.escape(SINGLE_SURNAMES)
    + r"])\s*[\u4e00-\u9fff](?:\s*[\u4e00-\u9fff])?(?![\u4e00-\u9fff])"
)

CONTEXT_PERSON_RE = re.compile(
    r"(?P<prefix>^|[与和及、，,；;（(])(?P<name>"
    + "|".join(map(re.escape, COMPOUND_SURNAMES))
    + r"[\u4e00-\u9fff]{1,2}|["
    + re.escape(SINGLE_SURNAMES)
    + r"][\u4e00-\u9fff]{1,2})(?="
    + r"就|因|向|与|和|及|、|，|,|；|;|之间|发生|签订|主张|认为|诉|申请|被|在|的|为|系|于|将|把|对|$)"
)

MASKED_PERSON_RE = re.compile(
    r"("
    + "|".join(map(re.escape, COMPOUND_SURNAMES))
    + r")[\u4e00-\u9fff]?某[\u4e00-\u9fff]?"
    + r"|(["
    + re.escape(SINGLE_SURNAMES)
    + r"])[\u4e00-\u9fff]?某[\u4e00-\u9fff]?"
)

ORG_RE = re.compile(
    r"[\u4e00-\u9fffA-Za-z0-9（）()·&＆\-]{1,40}(?:"
    + "|".join(map(re.escape, ORG_SUFFIXES))
    + r")"
)

LABEL_LINE_RE = re.compile(
    r"^(咨询人|答疑专家|作者|联系人|法定代表人|负责人|实际控制人|委托诉讼代理人|代理人|律师|"
    r"承办法官|审判员|书记员|当事人|原告|被告|上诉人|被上诉人|申请人|被申请人)[：:]"
)

BOILERPLATE_LINE_RE = re.compile(
    r"^(责任编辑|编辑|来源|发布时间|发布日期|浏览次数|阅读次数|点击量|分享到|分享至|字号|打印本页)[：:]"
)


class SimpleHTMLToText(HTMLParser):
    block_tags = {"p", "div", "section", "article", "li", "tr", "h1", "h2", "h3", "h4", "br"}
    skip_tags = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0
        self.title_parts: list[str] = []
        self.in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in self.skip_tags:
            self.skip_depth += 1
            return
        if tag == "title":
            self.in_title = True
        if tag in self.block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.skip_tags and self.skip_depth:
            self.skip_depth -= 1
            return
        if tag == "title":
            self.in_title = False
        if tag in self.block_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        if self.in_title:
            self.title_parts.append(data)
            return
        self.parts.append(data)

    @property
    def text(self) -> str:
        return normalize_text("".join(self.parts))

    @property
    def title(self) -> str:
        return normalize_inline_text("".join(self.title_parts))


class Anonymizer:
    def __init__(self, extra_entities: list[tuple[str, str]] | None = None, strict_person: bool = False):
        self.extra_entities = extra_entities or []
        self.strict_person = strict_person
        self.maps: dict[str, OrderedDict[str, str]] = {
            "person": OrderedDict(),
            "organization": OrderedDict(),
            "mobile": OrderedDict(),
            "id_card": OrderedDict(),
            "email": OrderedDict(),
            "credit_code": OrderedDict(),
            "custom": OrderedDict(),
        }
        self.labels = {
            "person": "自然人",
            "organization": "主体",
            "mobile": "手机号",
            "id_card": "身份证号",
            "email": "邮箱",
            "credit_code": "统一社会信用代码",
            "custom": "主体",
        }

    def anonymize(self, text: str) -> str:
        text = self._replace_contacts(text)
        text = self._replace_extra_entities(text)
        text = self._replace_organizations(text)
        text = self._replace_masked_people(text)
        text = self._replace_people_in_labeled_lines(text)
        if self.strict_person:
            text = self._replace_people_by_context(text)
            text = SPACED_PERSON_TOKEN_RE.sub(lambda m: self.placeholder("person", m.group(0)), text)
            text = PERSON_TOKEN_RE.sub(lambda m: self.placeholder("person", m.group(0)), text)
        return text

    def placeholder(self, entity_type: str, value: str) -> str:
        value = normalize_inline_text(value)
        if not value or value in PUBLIC_ORG_ALLOWLIST:
            return value
        mapping = self.maps[entity_type]
        if value not in mapping:
            mapping[value] = f"【{self.labels[entity_type]}{len(mapping) + 1}】"
        return mapping[value]

    def summary(self) -> dict[str, int]:
        return {key: len(value) for key, value in self.maps.items() if value}

    def _replace_contacts(self, text: str) -> str:
        patterns = [
            ("email", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
            ("mobile", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
            (
                "id_card",
                re.compile(
                    r"(?<![0-9Xx])\d{6}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])"
                    r"(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?![0-9Xx])"
                ),
            ),
            ("credit_code", re.compile(r"(?<![A-Z0-9])[0-9A-Z]{18}(?![A-Z0-9])")),
        ]
        for entity_type, pattern in patterns:
            text = pattern.sub(lambda m, t=entity_type: self.placeholder(t, m.group(0)), text)
        return text

    def _replace_extra_entities(self, text: str) -> str:
        for entity_type, value in sorted(self.extra_entities, key=lambda item: len(item[1]), reverse=True):
            entity_type = entity_type if entity_type in self.maps else "custom"
            if value.strip():
                text = re.sub(re.escape(value.strip()), self.placeholder(entity_type, value), text)
        return text

    def _replace_organizations(self, text: str) -> str:
        def repl(match: re.Match[str]) -> str:
            raw = match.group(0)
            prefix, entity = split_role_prefix(raw)
            if entity in PUBLIC_ORG_ALLOWLIST or entity in GENERIC_ORG_TERMS:
                return raw
            return prefix + self.placeholder("organization", entity)

        return ORG_RE.sub(repl, text)

    def _replace_masked_people(self, text: str) -> str:
        return MASKED_PERSON_RE.sub(lambda m: self.placeholder("person", m.group(0)), text)

    def _replace_people_by_context(self, text: str) -> str:
        def repl(match: re.Match[str]) -> str:
            name = match.group("name")
            if name in PERSON_STOPWORDS:
                return match.group(0)
            return match.group("prefix") + self.placeholder("person", name)

        return CONTEXT_PERSON_RE.sub(repl, text)

    def _replace_people_in_labeled_lines(self, text: str) -> str:
        output: list[str] = []
        for line in text.splitlines(keepends=True):
            if LABEL_LINE_RE.search(strip_markdown(line).strip()):
                line = SPACED_PERSON_TOKEN_RE.sub(lambda m: self.placeholder("person", m.group(0)), line)
                line = PERSON_TOKEN_RE.sub(lambda m: self.placeholder("person", m.group(0)), line)
            output.append(line)
        return "".join(output)


def split_role_prefix(raw: str) -> tuple[str, str]:
    prefix = ""
    entity = raw
    changed = True
    while changed:
        changed = False
        for role in ROLE_PREFIXES:
            if entity.startswith(role) and len(entity) > len(role) + 1:
                prefix += role
                entity = entity[len(role) :]
                changed = True
                break
    return prefix, entity


def normalize_inline_text(text: str) -> str:
    text = html_lib.unescape(text or "")
    text = text.replace("\ufeff", "").replace("\xa0", " ").replace("\u3000", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return text.strip()


def normalize_text(text: str) -> str:
    text = html_lib.unescape(text or "")
    text = text.replace("\ufeff", "").replace("\xa0", " ").replace("\u3000", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_markdown(text: str) -> str:
    return re.sub(r"[*_`#>\[\]【】]", "", text)


def read_text_file(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace"), "utf-8-replace"


def remove_yaml_front_matter(text: str) -> tuple[str, str]:
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            after = end + len("\n---")
            if after < len(text) and text[after : after + 1] == "\n":
                after += 1
            return text[: after], text[after:]
    return "", text


def extract_title(path: Path, text: str, html_title: str = "") -> str:
    yaml_title = extract_yaml_title(text)
    if yaml_title:
        return yaml_title
    if html_title:
        return html_title
    for pattern in (
        r"^\s*#\s+(.+?)\s*$",
        r"^\s*标题[：:]\s*(.+?)\s*$",
        r"^\s*题目[：:]\s*(.+?)\s*$",
    ):
        match = re.search(pattern, text, re.M)
        if match:
            return normalize_inline_text(match.group(1))
    for line in text.splitlines():
        line = normalize_inline_text(strip_markdown(line))
        if line:
            return line[:120]
    return path.stem


def extract_yaml_title(text: str) -> str:
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---", 4)
    if end == -1:
        return ""
    front = text[4:end]
    for line in front.splitlines():
        if line.startswith("title:"):
            return normalize_inline_text(line.split(":", 1)[1].strip().strip("\"'"))
    return ""


def is_promo_title(title: str, keywords: tuple[str, ...]) -> tuple[bool, str]:
    for keyword in keywords:
        if keyword and keyword in title:
            return True, keyword
    return False, ""


def clean_body(text: str) -> str:
    _, text = remove_yaml_front_matter(text)
    text = normalize_text(text)
    kept_lines: list[str] = []
    for line in text.splitlines():
        plain = normalize_inline_text(strip_markdown(line))
        if not plain:
            kept_lines.append("")
            continue
        if BOILERPLATE_LINE_RE.match(plain):
            continue
        if plain in {"打印本页", "关闭窗口", "返回顶部"}:
            continue
        kept_lines.append(line)
    cleaned = "\n".join(kept_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip() + "\n"


def html_to_markdownish(text: str) -> tuple[str, str]:
    parser = SimpleHTMLToText()
    parser.feed(text)
    parser.close()
    return parser.text, parser.title


def build_document(path: Path, source_text: str, args, extra_entities: list[tuple[str, str]]) -> tuple[str, dict, str]:
    html_title = ""
    if path.suffix.lower() in {".html", ".htm"}:
        body, html_title = html_to_markdownish(source_text)
    else:
        body = source_text

    title = extract_title(path, source_text, html_title=html_title)
    before_body = clean_body(body)
    strict_person = effective_strict_person(args)
    anonymizer = Anonymizer(extra_entities=extra_entities, strict_person=strict_person)
    clean_title = anonymizer.anonymize(title)
    before_body = drop_duplicate_title_heading(before_body, title)
    after_body = anonymizer.anonymize(before_body)

    before_hash = sha256(before_body.encode("utf-8")).hexdigest()
    after_hash = sha256(after_body.encode("utf-8")).hexdigest()
    processed_at = datetime.now().astimezone().isoformat(timespec="seconds")

    metadata = OrderedDict(
        [
            ("title", clean_title),
            ("original_filename", path.name),
            ("original_path", str(path.resolve())),
            ("source_extension", path.suffix.lower()),
            ("processed_at", processed_at),
            ("format", "markdown"),
            ("cleaned", True),
            ("anonymized", True),
            (
                "anonymization",
                OrderedDict(
                    [
                        ("method", "rule_based_regex"),
                        ("strict_person_regex", strict_person),
                        ("replacement_counts", anonymizer.summary()),
                    ]
                ),
            ),
            ("content_sha256_before", before_hash),
            ("content_sha256_after", after_hash),
        ]
    )
    document = render_yaml(metadata) + f"\n# {clean_title}\n\n" + after_body
    return document, anonymizer.summary(), clean_title


def effective_strict_person(args) -> bool:
    return bool(args.strict_person_regex or not args.conservative_person_regex)


def drop_duplicate_title_heading(text: str, title: str) -> str:
    lines = text.splitlines()
    if not lines:
        return text
    title_plain = normalize_inline_text(strip_markdown(title))
    first_plain = normalize_inline_text(strip_markdown(lines[0]).lstrip("#").strip())
    if title_plain and first_plain == title_plain:
        return "\n".join(lines[1:]).lstrip() + "\n"
    return text


def render_yaml(data: OrderedDict | dict) -> str:
    lines = ["---"]
    for key, value in data.items():
        lines.extend(render_yaml_item(str(key), value, 0))
    lines.append("---")
    return "\n".join(lines) + "\n"


def render_yaml_item(key: str, value, indent: int) -> list[str]:
    prefix = " " * indent
    if isinstance(value, (dict, OrderedDict)):
        if not value:
            return [f"{prefix}{key}: {{}}"]
        lines = [f"{prefix}{key}:"]
        for child_key, child_value in value.items():
            lines.extend(render_yaml_item(str(child_key), child_value, indent + 2))
        return lines
    if isinstance(value, list):
        if not value:
            return [f"{prefix}{key}: []"]
        return [f"{prefix}{key}:"] + [f"{prefix}  - {yaml_scalar(item)}" for item in value]
    return [f"{prefix}{key}: {yaml_scalar(value)}"]


def yaml_scalar(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def read_extra_entities(path: Path | None) -> list[tuple[str, str]]:
    if path is None:
        return []
    entities: list[tuple[str, str]] = []
    text, _ = read_text_file(path)
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "," in line:
            entity_type, value = [part.strip() for part in line.split(",", 1)]
        else:
            entity_type, value = "custom", line
        entities.append((entity_type, value))
    return entities


def collect_files(input_dir: Path, extensions: tuple[str, ...], exclude_dirs: set[str]) -> list[Path]:
    files: list[Path] = []
    for path in input_dir.rglob("*"):
        if not path.is_file():
            continue
        if any(part in exclude_dirs for part in path.relative_to(input_dir).parts[:-1]):
            continue
        if path.suffix.lower() in extensions:
            files.append(path)
    return sorted(files)


def output_path_for(path: Path, input_dir: Path, output_dir: Path, in_place: bool) -> Path:
    if in_place:
        return path
    rel = path.relative_to(input_dir)
    suffix = ".md" if path.suffix.lower() in {".txt", ".html", ".htm", ".markdown"} else path.suffix
    return (output_dir / rel).with_suffix(suffix)


def move_to_quarantine(path: Path, input_dir: Path, quarantine_dir: Path) -> Path:
    rel = path.relative_to(input_dir)
    target = quarantine_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target = target.with_name(f"{target.stem}_{datetime.now().strftime('%H%M%S')}{target.suffix}")
    shutil.move(str(path), str(target))
    return target


def write_report(output_root: Path, records: list[dict]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "total": len(records),
        "cleaned": sum(1 for record in records if record["action"] == "cleaned"),
        "filtered": sum(1 for record in records if record["action"].startswith("filtered")),
        "records": records,
    }
    (output_root / "cleaning_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = ["# 数据清洗报告", ""]
    lines.append(f"- 生成时间：{report['generated_at']}")
    lines.append(f"- 文件总数：{report['total']}")
    lines.append(f"- 已清洗：{report['cleaned']}")
    lines.append(f"- 已过滤：{report['filtered']}")
    lines.append("")
    for record in records:
        lines.append(f"- `{record['action']}` | {record.get('title', '')} | {record['source']}")
    (output_root / "cleaning_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_keywords(value: str | None) -> tuple[str, ...]:
    if not value:
        return DEFAULT_PROMO_KEYWORDS
    return tuple(item.strip() for item in re.split(r"[,，]", value) if item.strip())


def parse_extensions(value: str | None) -> tuple[str, ...]:
    if not value:
        return DEFAULT_EXTENSIONS
    extensions: list[str] = []
    for item in re.split(r"[,，]", value):
        item = item.strip().lower()
        if not item:
            continue
        extensions.append(item if item.startswith(".") else f".{item}")
    return tuple(extensions)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="批量清洗公开渠道下载的文章，添加 YAML 元信息，脱敏主体信息，并过滤推广广告文章。"
    )
    parser.add_argument("input_dir", help="待处理文件夹。")
    parser.add_argument("--output-dir", help="清洗结果输出目录。默认在输入目录旁创建 *_cleaned_时间戳。")
    parser.add_argument("--in-place", action="store_true", help="直接改写原文件；推广文章会移入隔离目录。")
    parser.add_argument("--delete-promos", action="store_true", help="即使不是 in-place，也处理源文件中的推广文章。")
    parser.add_argument("--hard-delete", action="store_true", help="真正删除推广文章；默认是移入隔离目录。")
    parser.add_argument("--quarantine-dir", help="推广文章隔离目录；默认在输入目录旁创建 *_filtered_promo_时间戳。")
    parser.add_argument("--extra-entities", help="自定义脱敏词表，每行：type,value 或直接写主体名称。")
    parser.add_argument(
        "--strict-person-regex",
        action="store_true",
        help="启用全文人名识别。当前默认已启用，保留该参数用于向前兼容。",
    )
    parser.add_argument(
        "--conservative-person-regex",
        action="store_true",
        help="使用保守人名识别，仅处理标签行、半匿名姓名和自定义词表，降低误伤。",
    )
    parser.add_argument(
        "--promo-keywords",
        help="推广标题关键词，逗号分隔；默认：荣登,祝贺,邀请,恭喜。",
    )
    parser.add_argument("--extensions", help="处理的扩展名，逗号分隔；默认：.md,.markdown,.txt,.html,.htm。")
    parser.add_argument("--dry-run", action="store_true", help="只扫描并输出报告，不改写、不复制、不删除文件。")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_dir = Path(args.input_dir).expanduser().resolve()
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"输入目录不存在或不是文件夹：{input_dir}", file=sys.stderr)
        return 2

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else input_dir.parent / f"{input_dir.name}_cleaned_{timestamp}"
    )
    quarantine_dir = (
        Path(args.quarantine_dir).expanduser().resolve()
        if args.quarantine_dir
        else input_dir.parent / f"{input_dir.name}_filtered_promo_{timestamp}"
    )
    report_dir = output_dir if not args.in_place else input_dir / "_cleaning_reports"
    keywords = parse_keywords(args.promo_keywords)
    extensions = parse_extensions(args.extensions)
    extra_entities = read_extra_entities(Path(args.extra_entities).expanduser() if args.extra_entities else None)
    exclude_dirs = {output_dir.name, quarantine_dir.name, "_cleaning_reports", "__pycache__"}

    files = collect_files(input_dir, extensions, exclude_dirs)
    records: list[dict] = []

    for path in files:
        source_text, encoding = read_text_file(path)
        html_title = ""
        title_source_text = source_text
        if path.suffix.lower() in {".html", ".htm"}:
            title_source_text, html_title = html_to_markdownish(source_text)
        title = extract_title(path, title_source_text, html_title=html_title)
        is_promo, matched_keyword = is_promo_title(title, keywords)

        if is_promo:
            action = "filtered"
            moved_to = ""
            if (args.in_place or args.delete_promos) and not args.dry_run:
                if args.hard_delete:
                    path.unlink()
                    action = "filtered_deleted"
                else:
                    moved_to = str(move_to_quarantine(path, input_dir, quarantine_dir))
                    action = "filtered_quarantined"
            records.append(
                {
                    "source": str(path),
                    "title": title,
                    "action": action,
                    "matched_keyword": matched_keyword,
                    "moved_to": moved_to,
                    "encoding": encoding,
                }
            )
            continue

        document, counts, clean_title = build_document(path, source_text, args, extra_entities)
        target = output_path_for(path, input_dir, output_dir, args.in_place)
        if not args.dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(document, encoding="utf-8")
        records.append(
            {
                "source": str(path),
                "target": str(target),
                "title": clean_title,
                "action": "cleaned",
                "anonymization_counts": counts,
                "encoding": encoding,
            }
        )

    if not args.dry_run:
        write_report(report_dir, records)
    else:
        print(json.dumps({"dry_run": True, "records": records}, ensure_ascii=False, indent=2))

    print(
        f"完成：扫描 {len(records)} 个文件，清洗 {sum(1 for r in records if r['action'] == 'cleaned')} 个，"
        f"过滤 {sum(1 for r in records if r['action'].startswith('filtered'))} 个。",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
