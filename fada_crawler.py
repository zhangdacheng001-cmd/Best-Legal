#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crawl "法答网精选答问" articles from www.court.gov.cn and save one
anonymized Markdown document per article.

Dependency: lxml
The script deliberately avoids requests/BeautifulSoup because they are not
available in the default Python environment on this machine.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import html as html_lib
import json
import re
import sys
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

try:
    from lxml import html
except ImportError as exc:  # pragma: no cover
    raise SystemExit("缺少依赖 lxml。请先运行：python3 -m pip install lxml") from exc


COURT_BASE = "https://www.court.gov.cn"
DEFAULT_QUERY = "法答网精选答问"
DEFAULT_OUTPUT_ROOT = Path("/Users/Mr.Z/工作区/1-数据库")
USER_AGENT = (
    "Mozilla/5.0 (compatible; FadaCrawler/1.0; "
    "+for legal research; polite-rate-limited)"
)

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
    "庾终暨居衡步都耿满弘匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂"
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
    r"^(咨询人|答疑专家|作者|联系人|法定代表人|负责人|实际控制人|委托诉讼代理人|代理人|律师|承办法官|审判员|书记员)[：:]"
)


@dataclasses.dataclass
class ArticleLink:
    url: str
    title: str = ""


@dataclasses.dataclass
class ParsedArticle:
    url: str
    title: str
    source: str
    published_at: str
    column: str
    article_id: str
    markdown_body: str
    raw_text_sha256: str


class Anonymizer:
    def __init__(self, extra_entities: list[tuple[str, str]] | None = None, strict_person: bool = False):
        self.strict_person = strict_person
        self.extra_entities = extra_entities or []
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

    def placeholder(self, entity_type: str, value: str) -> str:
        value = normalize_inline_text(value)
        if not value:
            return value
        if value in PUBLIC_ORG_ALLOWLIST:
            return value
        mapping = self.maps[entity_type]
        if value not in mapping:
            mapping[value] = f"【{self.labels[entity_type]}{len(mapping) + 1}】"
        return mapping[value]

    def anonymize(self, text: str) -> str:
        text = self._replace_contacts(text)
        text = self._replace_extra_entities(text)
        text = self._replace_organizations(text)
        text = self._replace_masked_people(text)
        text = self._replace_people_in_labeled_lines(text)
        if self.strict_person:
            text = PERSON_TOKEN_RE.sub(lambda m: self.placeholder("person", m.group(0)), text)
        return text

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
            value = value.strip()
            if not value:
                continue
            normalized_type = entity_type if entity_type in self.maps else "custom"
            text = re.sub(re.escape(value), self.placeholder(normalized_type, value), text)
        return text

    def _replace_organizations(self, text: str) -> str:
        def repl(match: re.Match[str]) -> str:
            raw = match.group(0)
            prefix, entity = split_role_prefix(raw)
            if entity in PUBLIC_ORG_ALLOWLIST:
                return raw
            # Avoid replacing common phrases that merely describe a generic entity type.
            if entity in GENERIC_ORG_TERMS:
                return raw
            return prefix + self.placeholder("organization", entity)

        return ORG_RE.sub(repl, text)

    def _replace_masked_people(self, text: str) -> str:
        return MASKED_PERSON_RE.sub(lambda m: self.placeholder("person", m.group(0)), text)

    def _replace_people_in_labeled_lines(self, text: str) -> str:
        lines = text.splitlines(keepends=True)
        output: list[str] = []
        for line in lines:
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
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return text.strip()


def normalize_block_text(text: str) -> str:
    text = html_lib.unescape(text or "")
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def strip_markdown(text: str) -> str:
    return re.sub(r"[*_`#>\[\]【】]", "", text)


def safe_filename(text: str, max_len: int = 90) -> str:
    text = normalize_inline_text(text)
    text = re.sub(r"[\\/:*?\"<>|]+", "_", text)
    text = re.sub(r"\s+", "_", text)
    text = text.strip("._ ")
    return text[:max_len] or "untitled"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fetch_html(url: str, timeout: int, retries: int) -> str:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
                },
            )
            with urlopen(req, timeout=timeout) as response:
                raw = response.read()
                charset = response.headers.get_content_charset() or sniff_charset(raw) or "utf-8"
                return raw.decode(charset, errors="replace")
        except HTTPError as exc:
            if 400 <= exc.code < 500:
                raise
            last_error = exc
        except (URLError, TimeoutError) as exc:
            last_error = exc
        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def sniff_charset(raw: bytes) -> str | None:
    head = raw[:2048].decode("ascii", errors="ignore")
    match = re.search(r"charset=[\"']?([A-Za-z0-9_\-]+)", head, re.I)
    return match.group(1) if match else None


def parse_html_doc(text: str):
    return html.fromstring(text)


def discover_by_search(query: str, pages: int, timeout: int, retries: int) -> list[ArticleLink]:
    links: list[ArticleLink] = []
    seen_urls: set[str] = set()
    seen_page_signatures: set[tuple[str, ...]] = set()
    for page in range(1, pages + 1):
        params = urlencode({"content": query, "page": page})
        url = f"{COURT_BASE}/search.html?{params}"
        doc = parse_html_doc(fetch_html(url, timeout=timeout, retries=retries))
        page_links: list[str] = []
        for node in doc.xpath('//div[contains(@class, "search_list")]//a[@href]'):
            title = normalize_inline_text("".join(node.xpath(".//text()"))) or normalize_inline_text(
                node.get("title", "")
            )
            href = urljoin(COURT_BASE, node.get("href"))
            if "/zixun/xiangqing/" not in href:
                continue
            if query and query not in title:
                continue
            page_links.append(href)
            if href not in seen_urls:
                links.append(ArticleLink(url=href, title=title))
                seen_urls.add(href)
        signature = tuple(page_links)
        if signature and signature in seen_page_signatures:
            break
        seen_page_signatures.add(signature)
    return links


def parse_article(url: str, html_text: str) -> ParsedArticle:
    doc = parse_html_doc(html_text)
    detail = first_node(doc.xpath('//div[contains(concat(" ", normalize-space(@class), " "), " detail ")]'))
    title = ""
    if detail is not None:
        title = first_text(detail.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " title ")]//text()'))
    if not title:
        title = first_text(doc.xpath("//title/text()"))
        title = re.sub(r"\s*-\s*中华人民共和国最高人民法院\s*$", "", title)

    message_text = ""
    if detail is not None:
        message_text = normalize_inline_text(
            " ".join(detail.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " detail_mes ")]//text()'))
        )
    source = regex_first(r"来源[:：]\s*([^\s]+)", message_text)
    published_at = regex_first(r"发布时间[:：]\s*([0-9]{4}-[0-9]{2}-[0-9]{2}(?:\s+[0-9]{2}:[0-9]{2}:[0-9]{2})?)", message_text)

    column = ""
    location = first_node(doc.xpath('//div[contains(concat(" ", normalize-space(@class), " "), " location ")]'))
    if location is not None:
        loc_parts = [normalize_inline_text(part) for part in location.xpath(".//text()")]
        loc_parts = [part for part in loc_parts if part and part not in {"所在位置：", ">"}]
        column = " > ".join(loc_parts)

    body_node = first_node(doc.xpath('//div[@id="zoom"]'))
    if body_node is None:
        body_node = first_node(doc.xpath('//div[contains(concat(" ", normalize-space(@class), " "), " txt_txt ")]'))
    if body_node is None:
        body_node = first_node(doc.xpath('//div[contains(concat(" ", normalize-space(@class), " "), " txt ")]'))
    if body_node is None:
        raise ValueError(f"未找到正文容器：{url}")

    blocks = list(iter_markdown_blocks(body_node, base_url=url))
    markdown_body = structure_blocks(blocks)
    raw_text = "\n".join(strip_markdown(block) for block in blocks)
    article_id = regex_first(r"/xiangqing/([0-9]+)\.html", url)

    return ParsedArticle(
        url=url,
        title=title,
        source=source,
        published_at=published_at,
        column=column,
        article_id=article_id,
        markdown_body=markdown_body,
        raw_text_sha256=sha256_text(raw_text),
    )


def first_node(nodes):
    return nodes[0] if nodes else None


def first_text(values: Iterable[str]) -> str:
    for value in values:
        text = normalize_inline_text(value)
        if text:
            return text
    return ""


def regex_first(pattern: str, text: str) -> str:
    match = re.search(pattern, text or "")
    return normalize_inline_text(match.group(1)) if match else ""


def iter_markdown_blocks(node, base_url: str) -> Iterable[str]:
    for child in node:
        tag = local_name(child.tag)
        if tag in {"script", "style"}:
            continue
        if tag in {"p", "li"}:
            text = normalize_block_text(render_inline(child, base_url=base_url))
            if text:
                yield text
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            text = normalize_inline_text(child.text_content())
            if text:
                level = min(int(tag[1]), 3)
                yield f"{'#' * level} {text}"
        elif tag == "table":
            table_md = render_table(child)
            if table_md:
                yield table_md
        elif tag in {"div", "section", "article", "ul", "ol"}:
            child_blocks = list(iter_markdown_blocks(child, base_url=base_url))
            if child_blocks:
                for block in child_blocks:
                    yield block
            else:
                text = normalize_block_text(render_inline(child, base_url=base_url))
                if text:
                    yield text
        else:
            text = normalize_block_text(render_inline(child, base_url=base_url))
            if text:
                yield text


def local_name(tag) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1].lower()


def render_inline(node, base_url: str, strong: bool = False) -> str:
    parts: list[str] = []

    def walk(current, is_strong: bool = False) -> None:
        if current.text:
            parts.append(mark_text(current.text, is_strong))
        for child in current:
            tag = local_name(child.tag)
            child_strong = is_strong or tag in {"strong", "b"}
            if tag == "br":
                parts.append("\n")
            elif tag == "img":
                src = child.get("src")
                alt = normalize_inline_text(child.get("alt", "图片"))
                if src:
                    parts.append(f"![{alt}]({urljoin(base_url, src)})")
            elif tag == "a":
                label = normalize_inline_text(child.text_content())
                href = child.get("href")
                if label and href and not href.startswith("javascript:"):
                    parts.append(f"[{label}]({urljoin(base_url, href)})")
                else:
                    walk(child, child_strong)
            else:
                walk(child, child_strong)
            if child.tail:
                parts.append(mark_text(child.tail, is_strong))

    walk(node, strong)
    return "".join(parts)


def mark_text(text: str, strong: bool) -> str:
    if not strong:
        return text
    stripped = text.strip()
    if not stripped:
        return text
    leading = text[: len(text) - len(text.lstrip())]
    trailing = text[len(text.rstrip()) :]
    return f"{leading}**{stripped}**{trailing}"


def render_table(table) -> str:
    rows: list[list[str]] = []
    for tr in table.xpath(".//tr"):
        cells = [normalize_inline_text(cell.text_content()) for cell in tr.xpath("./th|./td")]
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    header = normalized[0]
    lines = [
        "| " + " | ".join(escape_table_cell(cell) for cell in header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in normalized[1:]:
        lines.append("| " + " | ".join(escape_table_cell(cell) for cell in row) + " |")
    return "\n".join(lines)


def escape_table_cell(text: str) -> str:
    return text.replace("|", "\\|")


def structure_blocks(blocks: list[str]) -> str:
    output: list[str] = []
    for block in blocks:
        plain = strip_markdown(block).strip()
        if not plain or plain.startswith("责任编辑："):
            continue
        if re.match(r"^开栏的话[:：]", plain):
            output.append("## " + strip_outer_bold(block))
        elif re.match(r"^问题[0-9一二三四五六七八九十百]+[:：]", plain):
            output.append("## " + strip_outer_bold(block))
        else:
            output.append(block)
    return "\n\n".join(output).strip() + "\n"


def strip_outer_bold(text: str) -> str:
    text = text.strip()
    if text.startswith("**") and text.endswith("**"):
        return text[2:-2]
    return text


def build_markdown(article: ParsedArticle, anonymizer: Anonymizer) -> tuple[str, dict[str, int], str]:
    clean_title = anonymizer.anonymize(article.title)
    clean_body = anonymizer.anonymize(article.markdown_body)
    fetched_at = datetime.now().astimezone().isoformat(timespec="seconds")
    metadata = OrderedDict(
        [
            ("title", clean_title),
            ("site", "中华人民共和国最高人民法院"),
            ("source_url", article.url),
            ("source", article.source),
            ("published_at", article.published_at),
            ("column", article.column),
            ("article_id", article.article_id),
            ("fetched_at", fetched_at),
            ("format", "markdown"),
            ("anonymized", True),
            (
                "anonymization",
                OrderedDict(
                    [
                        ("method", "rule_based_regex"),
                        ("strict_person_regex", anonymizer.strict_person),
                        ("replacement_counts", anonymizer.summary()),
                    ]
                ),
            ),
            ("raw_text_sha256", article.raw_text_sha256),
        ]
    )
    markdown = render_yaml(metadata) + f"\n# {clean_title}\n\n" + clean_body
    return markdown, anonymizer.summary(), clean_title


def render_yaml(data: OrderedDict | dict, indent: int = 0) -> str:
    if indent == 0:
        lines = ["---"]
        for key, value in data.items():
            lines.extend(render_yaml_item(str(key), value, indent))
        lines.append("---")
        return "\n".join(lines) + "\n"
    raise NotImplementedError


def render_yaml_item(key: str, value, indent: int) -> list[str]:
    prefix = " " * indent
    if isinstance(value, (dict, OrderedDict)):
        lines = [f"{prefix}{key}:"]
        if not value:
            lines[-1] += " {}"
            return lines
        for child_key, child_value in value.items():
            lines.extend(render_yaml_item(str(child_key), child_value, indent + 2))
        return lines
    if isinstance(value, list):
        lines = [f"{prefix}{key}:"]
        if not value:
            lines[-1] += " []"
            return lines
        for item in value:
            lines.append(f"{prefix}  - {yaml_scalar(item)}")
        return lines
    return [f"{prefix}{key}: {yaml_scalar(value)}"]


def yaml_scalar(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def read_url_file(path: Path) -> list[ArticleLink]:
    links: list[ArticleLink] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "," in line:
            url, title = [part.strip() for part in line.split(",", 1)]
            links.append(ArticleLink(url=url, title=title))
        else:
            links.append(ArticleLink(url=line))
    return links


def read_extra_entities(path: Path | None) -> list[tuple[str, str]]:
    if path is None:
        return []
    entities: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "," in line:
            entity_type, value = [part.strip() for part in line.split(",", 1)]
        else:
            entity_type, value = "custom", line
        entities.append((entity_type, value))
    return entities


def dedupe_links(links: Iterable[ArticleLink]) -> list[ArticleLink]:
    seen: set[str] = set()
    output: list[ArticleLink] = []
    for link in links:
        normalized = normalize_url(link.url)
        if not normalized or normalized in seen:
            continue
        output.append(ArticleLink(url=normalized, title=link.title))
        seen.add(normalized)
    return output


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    parsed = urlparse(url)
    if not parsed.scheme:
        url = urljoin(COURT_BASE, url)
    return url


def choose_output_dir(args: argparse.Namespace) -> Path:
    if args.output_dir:
        return Path(args.output_dir).expanduser()
    root = Path(args.output_root).expanduser()
    folder_name = args.folder_name or f"法答网问答精选_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    return root / folder_name


def write_manifest(output_dir: Path, records: list[dict]) -> None:
    manifest = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "article_count": len(records),
        "articles": records,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = ["# 法答网问答精选抓取清单", ""]
    for record in records:
        lines.append(
            f"- [{record['title']}]({record['filename']}) | {record.get('published_at') or '无发布时间'} | {record['url']}"
        )
    (output_dir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="抓取最高人民法院网站“法答网精选答问”文章，清洗脱敏后逐篇保存为 Markdown。",
    )
    parser.add_argument("--url", action="append", default=[], help="单篇文章 URL，可重复传入。")
    parser.add_argument("--url-file", help="URL 清单文件；每行一个 URL，或 URL,标题。")
    parser.add_argument(
        "--search",
        nargs="?",
        const=DEFAULT_QUERY,
        default=None,
        help="通过最高法站内搜索发现文章；不写关键词时默认“法答网精选答问”。",
    )
    parser.add_argument("--pages", type=int, default=2, help="站内搜索抓取页数，默认 2。")
    parser.add_argument("--max-articles", type=int, help="最多抓取多少篇文章。")
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help=f"输出根目录，默认 {DEFAULT_OUTPUT_ROOT}",
    )
    parser.add_argument("--output-dir", help="指定完整输出目录；设置后不再自动创建时间戳目录。")
    parser.add_argument("--folder-name", help="在 output-root 下创建的文件夹名称。")
    parser.add_argument("--extra-entities", help="自定义脱敏词表，每行：type,value 或直接写主体名称。")
    parser.add_argument(
        "--strict-person-regex",
        action="store_true",
        help="启用更激进的人名识别；可能误伤普通中文词语，建议人工复核。",
    )
    parser.add_argument("--delay", type=float, default=1.0, help="每篇文章之间的间隔秒数，默认 1。")
    parser.add_argument("--timeout", type=int, default=20, help="单次请求超时时间秒数，默认 20。")
    parser.add_argument("--retries", type=int, default=2, help="失败重试次数，默认 2。")
    parser.add_argument("--dry-run", action="store_true", help="只发现链接，不下载正文和写文件。")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    links: list[ArticleLink] = []

    for url in args.url:
        links.append(ArticleLink(url=url))
    if args.url_file:
        links.extend(read_url_file(Path(args.url_file).expanduser()))

    if args.search is not None:
        links.extend(discover_by_search(args.search, args.pages, args.timeout, args.retries))

    if not links:
        print("未传入 URL，默认使用站内搜索抓取“法答网精选答问”。", file=sys.stderr)
        links.extend(discover_by_search(DEFAULT_QUERY, args.pages, args.timeout, args.retries))

    links = dedupe_links(links)
    if args.max_articles:
        links = links[: args.max_articles]

    if args.dry_run:
        for link in links:
            print(f"{link.url}\t{link.title}")
        return 0

    output_dir = choose_output_dir(args)
    output_dir.mkdir(parents=True, exist_ok=True)
    extra_entities = read_extra_entities(Path(args.extra_entities).expanduser() if args.extra_entities else None)

    records: list[dict] = []
    for index, link in enumerate(links, start=1):
        print(f"[{index}/{len(links)}] 抓取：{link.url}", file=sys.stderr)
        html_text = fetch_html(link.url, timeout=args.timeout, retries=args.retries)
        article = parse_article(link.url, html_text)
        anonymizer = Anonymizer(extra_entities=extra_entities, strict_person=args.strict_person_regex)
        markdown, counts, clean_title = build_markdown(article, anonymizer)
        filename = f"{article.article_id or index:0>6}_{safe_filename(clean_title)}.md"
        path = output_dir / filename
        path.write_text(markdown, encoding="utf-8")
        records.append(
            {
                "title": clean_title,
                "filename": filename,
                "url": article.url,
                "published_at": article.published_at,
                "source": article.source,
                "article_id": article.article_id,
                "anonymization_counts": counts,
            }
        )
        if index < len(links) and args.delay > 0:
            time.sleep(args.delay)

    write_manifest(output_dir, records)
    print(f"完成：{len(records)} 篇文章已保存至 {output_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
