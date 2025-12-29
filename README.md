# 论文信息搜集工具

这是一个自动化工具，用于从DBLP网站收集会议论文信息。

## 功能特点

- 自动访问DBLP会议页面
- 自动导出JSON格式的论文数据
- 提取论文标题、作者、会议简称和年份
- 支持多URL会议（如ASPLOS）
- 自动处理2025年和2024年的数据
- 特殊处理MLSys（只有2024年）
- 导出为CSV格式

## 安装依赖

```bash
pip install -r requirements.txt
```

## 安装ChromeDriver

程序需要Chrome浏览器和ChromeDriver。你可以：

1. **自动安装（推荐）**：使用webdriver-manager（需要修改代码）
2. **手动安装**：
   - 下载ChromeDriver：https://chromedriver.chromium.org/
   - 确保ChromeDriver在系统PATH中

## 使用方法

### 方法1：直接运行主程序

```bash
python paper_scraper.py
```

### 方法2：使用快速运行脚本（推荐）

```bash
python run.py
```

### 程序执行流程

程序会自动执行以下步骤：

1. **加载会议配置**：从`conferences.json`读取会议列表
2. **处理每个会议**：
   - 先处理2025年的数据
   - 再处理2024年的数据
   - 特殊情况：MLSys只处理2024年
3. **访问DBLP页面**：
   - 优先使用API直接获取JSON数据（更快）
   - 如果API失败，使用Selenium自动化浏览器
4. **提取论文信息**：
   - 论文标题
   - 作者列表
   - 会议简称
   - 年份
5. **保存结果**：将所有数据保存到`papers.csv`文件

### 运行模式

- **有界面模式**（默认）：`headless=False` - 会显示浏览器窗口，方便调试
- **无头模式**：修改代码中的`headless=True` - 后台运行，不显示浏览器窗口

## 输出格式

CSV文件包含以下列：
- `title`: 论文标题
- `authors`: 作者（多个作者用分号分隔）
- `conference`: 会议简称
- `year`: 年份

## 使用Semantic Scholar API丰富论文信息

在获得基础论文信息后，可以使用Semantic Scholar API获取论文的abstract和引用量：

### 运行丰富脚本

```bash
python run_enrich.py
```

或者直接运行：

```bash
python enrich_with_semantic_scholar.py
```

### 命令行参数

```bash
# 处理所有论文
python run_enrich.py

# 只处理前100篇论文
python run_enrich.py --max-papers 100

# 从第1000行开始处理（断点续传）
python run_enrich.py --start-from 1000

# 从第1000行开始，处理50篇
python run_enrich.py --start-from 1000 --max-papers 50

# 指定输入和输出文件
python run_enrich.py --input papers.csv --output papers_enriched.csv
```

### 功能说明

- `--max-papers`: 限制处理的论文数量，处理完最后一篇时会自动保存
- `--start-from`: 从指定行开始处理（用于断点续传）
- 程序每50篇自动保存一次进度
- **处理完最后一篇论文时一定会保存**（无论是否是50的倍数）

### 输出格式

丰富后的CSV文件（`papers_enriched.csv`）包含以下列：
- `title`: 论文标题
- `authors`: 作者（多个作者用分号分隔）
- `conference`: 会议简称
- `year`: 年份
- `abstract`: 论文摘要（从Semantic Scholar获取）
- `citationCount`: 引用量（从Semantic Scholar获取）

### 注意事项

- API频率限制：1请求/秒，程序会自动控制请求频率
- 处理大量论文需要较长时间（约1秒/篇）
- 程序每50篇自动保存一次进度，可以安全中断
- 如果某篇论文在Semantic Scholar中找不到，abstract和citationCount将为空/0

## 注意事项

- 程序需要网络连接访问DBLP网站
- 运行时间取决于网络速度和会议数量
- 建议在网络稳定时运行
- 如果某个会议数据获取失败，程序会继续处理下一个会议

## 配置说明

会议列表配置在`conferences.json`文件中，格式如下：

```json
{
  "id": 1,
  "abbreviation": "PPoPP",
  "full_name": "会议全称",
  "publisher": "出版社",
  "direction": "方向",
  "dblp_urls": ["URL1", "URL2"],
  "only_2024": false  // 可选，MLSys设为true
}
```

