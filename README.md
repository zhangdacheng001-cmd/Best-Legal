# 法答网问答精选抓取脚本

本工具用于从中华人民共和国最高人民法院网站公开页面抓取“法答网精选答问”文章，并将每篇文章保存为独立 Markdown 文档。输出文档包含 YAML 元信息，并对文章中涉及的自然人、公司、律所、银行等主体信息进行规则化脱敏处理。

## 一、选择该数据源的理由及简介

### 1. 数据源简介

“法答网精选答问”是最高人民法院从法答网咨询答疑中遴选并公开发布的法律适用问答内容。公开页面主要发布于最高人民法院官网 `www.court.gov.cn` 的新闻详情页，例如：

```text
https://www.court.gov.cn/zixun/xiangqing/434921.html
```

该类文章通常包括以下内容：

- 栏目说明或开栏说明；
- 若干法律适用问题；
- 对应的答疑意见；
- 咨询人、答疑专家及其所在法院或部门；
- 来源、发布时间、栏目位置等网页元信息。

### 2. 选择理由

- **权威性较强**：页面来源为最高人民法院官网，内容来自最高人民法院公开发布的信息，适合作为法律研究、类案规则整理、法律适用知识库建设的基础数据。
- **结构相对稳定**：文章详情页通常采用统一的标题、来源、发布时间、正文容器结构，便于自动化采集和后续解析。
- **法律适用价值较高**：问答内容围绕审判实践中的具体法律适用问题展开，包含裁判思路、法律依据、司法政策取向和实务提示。
- **适合知识库入库**：每篇文章可拆分为 Markdown 文档，并通过 YAML 元信息记录标题、来源、发布时间、原始链接、脱敏状态等字段，便于检索、向量化和后续人工校验。

**注意**：本脚本仅面向公开网页数据采集。使用者应遵守目标网站访问规则、数据合规要求及内部数据治理规范，不应进行高频访问、绕过访问限制或抓取非公开数据。

## 二、数据采集方法的详细说明

### 1. 采集范围

脚本支持两种采集方式：

- **精准 URL 采集**：传入一篇或多篇最高法文章详情页 URL。
- **站内搜索发现**：通过最高法站内搜索关键词“法答网精选答问”自动发现文章详情页链接，再逐篇抓取。

### 2. 采集流程

脚本的主要采集流程如下：

1. 读取用户输入的 URL、URL 清单文件或站内搜索关键词。
2. 如启用站内搜索，访问：

```text
https://www.court.gov.cn/search.html?content=法答网精选答问&page=1
```

3. 从搜索结果页中提取 `/zixun/xiangqing/*.html` 格式的文章链接。
4. 对链接进行去重，避免重复抓取同一文章。
5. 逐篇访问文章详情页。
6. 使用 `lxml.html` 解析 HTML。
7. 提取文章标题、来源、发布时间、栏目位置、文章编号和正文内容。
8. 将正文转换为 Markdown。
9. 执行清洗与脱敏。
10. 为每篇文章写入独立 `.md` 文件，同时生成 `index.md` 和 `manifest.json`。

### 3. 请求方式与频率控制

脚本使用 Python 标准库 `urllib.request` 发起 HTTP 请求，并设置常规浏览器 User-Agent。默认每篇文章之间间隔 `1` 秒，避免对目标网站造成不必要压力。

可通过参数调整访问间隔：

```bash
python3 fada_crawler.py --search "法答网精选答问" --pages 2 --delay 2
```

### 4. 主要命令

抓取单篇文章：

```bash
python3 fada_crawler.py --url "https://www.court.gov.cn/zixun/xiangqing/434921.html"
```

按 URL 清单抓取：

```bash
python3 fada_crawler.py --url-file urls.txt
```

通过站内搜索批量抓取：

```bash
python3 fada_crawler.py --search "法答网精选答问" --pages 2
```

只查看即将抓取的链接，不写入文件：

```bash
python3 fada_crawler.py --search "法答网精选答问" --pages 2 --dry-run
```

指定输出文件夹名称：

```bash
python3 fada_crawler.py --search "法答网精选答问" --pages 2 --folder-name "法答网问答精选_第一轮"
```

### 5. 输出目录

默认输出到：

```text
/Users/Mr.Z/工作区/1-数据库
```

如未指定 `--output-dir`，脚本会在上述目录下自动创建时间戳文件夹：

```text
/Users/Mr.Z/工作区/1-数据库/法答网问答精选_YYYYMMDD_HHMMSS/
```

输出结构示例：

```text
法答网问答精选_YYYYMMDD_HHMMSS/
  434921_法答网精选答问（第六批）.md
  index.md
  manifest.json
```

## 三、数据清洗方法的详细说明

### 1. 页面结构解析

脚本优先从最高法文章详情页中识别以下结构：

- 标题：`div.title`；
- 元信息：`div.detail_mes`，主要提取来源和发布时间；
- 正文：`div#zoom` 或 `div.txt_txt`；
- 栏目位置：`div.location`；
- 文章编号：从 URL 中的 `/xiangqing/{article_id}.html` 提取。

如页面结构发生小幅变化，脚本会按候选容器顺序降级查找正文，尽量保证可用性。

### 2. 正文内容清洗

脚本会移除或规避以下网页噪音：

- 顶部导航；
- 搜索框；
- 字号切换；
- 打印按钮；
- 页脚信息；
- 脚本、样式等非正文元素；
- “责任编辑”等非核心正文内容。

### 3. 文本规范化

脚本会对正文进行如下规范化处理：

- 将 HTML 实体还原为可读文本；
- 将全角空格、不间断空格统一为空格；
- 合并多余空白；
- 保留自然段落；
- 将正文中的加粗文本转换为 Markdown `**文本**`；
- 将“问题1：”“问题2：”等段落提升为二级标题；
- 将“开栏的话：”提升为二级标题；
- 将图片转换为 Markdown 图片语法；
- 将表格转换为 Markdown 表格。

### 4. 元信息整理

每篇文章都会生成 YAML front matter，字段包括：

```yaml
---
title: "法答网精选答问（第六批）"
site: "中华人民共和国最高人民法院"
source_url: "https://www.court.gov.cn/zixun/xiangqing/434921.html"
source: "人民法院报"
published_at: "2024-06-13 20:04:37"
column: "首页 > 最高人民法院新闻"
article_id: "434921"
fetched_at: "2026-06-28T..."
format: "markdown"
anonymized: true
anonymization:
  method: "rule_based_regex"
  strict_person_regex: false
  replacement_counts:
    person: 10
raw_text_sha256: "..."
---
```

其中：

- `source_url` 用于追溯原始网页；
- `published_at` 记录网页发布时间；
- `fetched_at` 记录抓取时间；
- `raw_text_sha256` 用于校验原始正文文本是否发生变化；
- `anonymization.replacement_counts` 记录各类脱敏替换数量。

## 四、脱敏处理方法的详细说明

### 1. 脱敏目标

脚本默认对以下信息进行脱敏：

- 自然人姓名；
- 已半匿名的自然人姓名，例如“刘某魁”“孙某梅”；
- 公司、律所、银行、保险公司、证券公司、基金公司、合伙企业等具体机构名称；
- 手机号；
- 身份证号；
- 邮箱；
- 统一社会信用代码；
- 用户自定义主体词表中的名称。

### 2. 脱敏替换规则

脚本采用规则化正则替换，并在同一篇文档内保持占位符一致。示例：

```text
刘某魁、孙某梅非法买卖枪支案
```

会被替换为：

```text
【自然人1】、【自然人2】非法买卖枪支案
```

再如：

```text
某某进出口有限公司
```

会被替换为：

```text
【主体1】
```

不同类型的占位符包括：

- `【自然人1】`、`【自然人2】`；
- `【主体1】`、`【主体2】`；
- `【手机号1】`；
- `【身份证号1】`；
- `【邮箱1】`；
- `【统一社会信用代码1】`。

### 3. 默认稳健模式

默认模式偏稳健，优先减少误伤：

- 对“咨询人：”“答疑专家：”“作者：”“联系人：”等标签行中的姓名进行识别和替换；
- 对“某某”式半匿名姓名进行进一步统一脱敏；
- 对带有明确组织后缀的具体主体名称进行脱敏；
- 保留“最高人民法院”“人民法院报”等公开机构名称；
- 保留“保险公司”“银行”“公司”等泛称，避免把普通类型词误替换为具体主体。

### 4. 严格人名识别模式

如需更激进地识别全文中的中文姓名，可启用：

```bash
python3 fada_crawler.py --url-file urls.txt --strict-person-regex
```

**注意**：严格模式可能将部分普通中文词语误判为姓名，建议在批量入库前抽样复核。

### 5. 自定义脱敏词表

如已有特定主体清单，可通过 `--extra-entities` 传入自定义词表：

```bash
python3 fada_crawler.py --url-file urls.txt --extra-entities extra_entities.example.txt
```

词表格式支持两种：

```text
person,张三
organization,宁波某某进出口有限公司
浙江某某律师事务所
```

说明：

- 第一列为类型，支持 `person`、`organization`、`custom`；
- 不写类型时默认按 `custom` 处理；
- 自定义词表优先于通用规则执行。

### 6. 脱敏局限

规则化脱敏不能替代人工审核，尤其在以下场景中可能存在遗漏或误伤：

- 自然人姓名不在标签行中，且未启用严格模式；
- 主体名称缺少典型组织后缀；
- 页面中存在非常规排版、图片文字或附件内容；
- 公司简称、品牌名、商号与普通词语混用。

因此，建议将脚本输出作为“初步清洗稿”，在正式入库、对外分享或用于模型训练前进行抽样复核。

## 五、本地文章清洗与脱敏脚本

除 `fada_crawler.py` 外，本仓库还提供独立的 `article_cleaner.py`，用于处理已经从公开渠道下载到本地的文章文件。该脚本不负责抓取网页，只负责对指定文件夹内的文章进行批量清洗、脱敏、YAML 元信息编制和推广文章过滤。

### 1. 适用场景

适用于以下工作流：

1. 已从公开渠道下载文章到本地工作区；
2. 需要对某个文件夹范围内的文章进行集中批量处理；
3. 需要将自然人、公司、律所、银行等主体信息替换为占位符；
4. 需要为每个文档补充 YAML 元信息；
5. 需要过滤明显推广、广告、活动邀请、祝贺类文章。

默认支持的文件类型：

```text
.md, .markdown, .txt, .html, .htm
```

### 2. 基本命令

将指定目录中的文章清洗到一个新的输出目录，原文件不变：

```bash
python3 article_cleaner.py "/Users/Mr.Z/工作区/待清洗文章"
```

指定输出目录：

```bash
python3 article_cleaner.py "/Users/Mr.Z/工作区/待清洗文章" --output-dir "/Users/Mr.Z/工作区/清洗后文章"
```

只扫描并预览处理结果，不写入、不删除：

```bash
python3 article_cleaner.py "/Users/Mr.Z/工作区/待清洗文章" --dry-run
```

直接改写原文件：

```bash
python3 article_cleaner.py "/Users/Mr.Z/工作区/待清洗文章" --in-place
```

### 3. 推广文章过滤与删除规则

脚本会读取每篇文章标题。如果标题中出现以下默认关键词，会识别为明显推广或广告文章：

```text
荣登, 祝贺, 邀请, 恭喜
```

普通清洗模式下，推广文章不会写入清洗后的输出目录，原文件保持不变。

如需处理源文件，可使用：

```bash
python3 article_cleaner.py "/Users/Mr.Z/工作区/待清洗文章" --delete-promos
```

默认不是硬删除，而是移入隔离目录，便于复核和恢复。若确需真正删除，可使用：

```bash
python3 article_cleaner.py "/Users/Mr.Z/工作区/待清洗文章" --delete-promos --hard-delete
```

如需自定义推广关键词：

```bash
python3 article_cleaner.py "/Users/Mr.Z/工作区/待清洗文章" --promo-keywords "荣登,祝贺,邀请,恭喜,喜讯,报名"
```

### 4. YAML 元信息

每个清洗后的文档都会写入 YAML front matter，示例：

```yaml
---
title: "某法律实务文章"
original_filename: "article.md"
original_path: "/Users/Mr.Z/工作区/待清洗文章/article.md"
source_extension: ".md"
processed_at: "2026-06-28T..."
format: "markdown"
cleaned: true
anonymized: true
anonymization:
  method: "rule_based_regex"
  strict_person_regex: true
  replacement_counts:
    person: 2
    organization: 1
content_sha256_before: "..."
content_sha256_after: "..."
---
```

### 5. 脱敏规则

`article_cleaner.py` 使用与抓取脚本相近的规则化脱敏逻辑：

- 对自然人姓名、已半匿名姓名进行替换；
- 对公司、律所、银行、保险公司、证券公司、基金公司、合伙企业等具体主体名称进行替换；
- 对手机号、身份证号、邮箱、统一社会信用代码进行替换；
- 对用户自定义词表中的主体名称进行替换；
- 默认保留“公司”“银行”“保险公司”等泛称，降低误伤。

使用自定义脱敏词表：

```bash
python3 article_cleaner.py "/Users/Mr.Z/工作区/待清洗文章" --extra-entities extra_entities.example.txt
```

默认会启用全文人名识别，以尽量覆盖正文中的自然人姓名。若文章类型复杂、担心误伤普通中文词语，可改用保守模式：

```bash
python3 article_cleaner.py "/Users/Mr.Z/工作区/待清洗文章" --conservative-person-regex
```

**注意**：全文人名识别可能误伤普通中文词语，建议先用 `--dry-run` 或小范围目录测试；如果误伤较多，再切换为 `--conservative-person-regex`。

### 6. 清洗报告

脚本会生成：

```text
cleaning_report.json
cleaning_report.md
```

报告中会记录每个文件的处理结果，包括：

- 原始文件路径；
- 输出文件路径；
- 文章标题；
- 是否被过滤；
- 命中的推广关键词；
- 脱敏替换数量。

## 六、运行环境

依赖：

```text
Python 3.9+
lxml
```

本脚本刻意避免使用 `requests`、`BeautifulSoup`、`PyYAML` 等额外依赖，以便在默认 Python 环境中更容易运行。

如缺少 `lxml`，可安装：

```bash
python3 -m pip install lxml
```

## 七、文件说明

```text
fada_crawler.py              主脚本
article_cleaner.py           本地文章批量清洗与脱敏脚本
urls.txt                     示例 URL 清单
extra_entities.example.txt   自定义脱敏词表示例
README.md                    使用说明
```

## 八、合规与频率提示

- 仅采集最高人民法院官网公开页面；
- 建议保留默认请求间隔或适当调大 `--delay`；
- 不建议并发抓取；
- 不应绕过网站访问限制；
- 批量入库前建议进行人工抽样复核；
- 涉及个人信息、主体信息和法律数据使用时，应遵守适用的数据合规、律师执业规范及内部保密要求。
