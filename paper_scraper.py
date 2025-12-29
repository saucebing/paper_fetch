#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
论文信息搜集工具
从DBLP网站自动收集会议论文信息
"""

import json
import csv
import time
import re
import os
from typing import List, Dict, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import urllib.parse
import requests


class PaperScraper:
    def __init__(self, headless: bool = True, download_dir: str = "./downloads"):
        """
        初始化爬虫
        
        Args:
            headless: 是否使用无头模式（默认True，因为优先使用API）
            download_dir: 下载目录
        """
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
        self.headless = headless
        self.driver = None  # 延迟初始化，只在需要时创建
        self.papers = []  # 存储所有论文信息
        
    def _init_driver(self):
        """延迟初始化Selenium WebDriver（只在需要时调用）"""
        if self.driver is not None:
            return
        
        # 配置Chrome选项
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        
        # 尝试找到Chrome二进制文件
        chrome_paths = [
            "/root/chrome-linux64/chrome",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
            "/usr/bin/chrome",
        ]
        
        chrome_binary = None
        for path in chrome_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                chrome_binary = path
                break
        
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
            print(f"使用Chrome二进制: {chrome_binary}")
        else:
            print("警告: 未找到Chrome二进制文件，尝试使用系统默认")
        
        # 设置下载目录
        prefs = {
            "download.default_directory": os.path.abspath(self.download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        try:
            # 使用webdriver-manager自动管理ChromeDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.implicitly_wait(10)
            print("Selenium WebDriver初始化成功")
        except Exception as e:
            print(f"警告: Selenium WebDriver初始化失败: {e}")
            print("将仅使用API方式获取数据（某些页面可能无法访问）")
            self.driver = None
        
    def load_conferences(self, config_file: str = "conferences.json") -> List[Dict]:
        """加载会议配置"""
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_export_url(self, dblp_url: str) -> str:
        """
        从DBLP页面URL生成导出JSON的URL
        
        DBLP的导出URL格式是：
        https://dblp.org/search/publ/api?q=toc:db/conf/{conf_name}/{conf_year}.bht:&h=1000&format=json
        """
        # 解析URL
        match = re.search(r'/conf/([^/]+)/([^/]+)\.html', dblp_url)
        if match:
            conf_name = match.group(1)
            conf_year = match.group(2)
            # 构建导出URL（使用toc格式）
            query = f"toc:db/conf/{conf_name}/{conf_year}.bht:"
            export_url = f"https://dblp.org/search/publ/api?q={urllib.parse.quote(query)}&h=1000&format=json"
            return export_url
        
        # 如果是搜索URL（如MLSys）
        if 'search' in dblp_url:
            # 解析搜索参数
            parsed = urllib.parse.urlparse(dblp_url)
            query_params = urllib.parse.parse_qs(parsed.query)
            if 'q' in query_params:
                query = query_params['q'][0]
                export_url = f"https://dblp.org/search/publ/api?q={urllib.parse.quote(query)}&h=1000&format=json"
                return export_url
        
        return None
    
    def download_json(self, dblp_url: str) -> Dict[str, Any]:
        """
        访问DBLP页面并下载JSON数据
        
        Args:
            dblp_url: DBLP页面URL
            
        Returns:
            解析后的JSON数据
        """
        try:
            # 方法1: 直接使用API导出URL（使用requests，更快）
            export_url = self.get_export_url(dblp_url)
            if export_url:
                print(f"  访问导出API: {export_url}")
                try:
                    response = requests.get(export_url, timeout=30)
                    response.raise_for_status()
                    data = response.json()
                    if data:
                        return data
                except requests.exceptions.RequestException as e:
                    print(f"  API请求失败: {e}")
                except json.JSONDecodeError as e:
                    print(f"  JSON解析失败: {e}")
            
            # 方法2: 使用Selenium访问页面并点击导出按钮
            # 确保driver已初始化
            self._init_driver()
            if self.driver is None:
                print(f"  Selenium不可用，跳过页面访问")
                return None
                
            print(f"  使用Selenium访问DBLP页面: {dblp_url}")
            self.driver.get(dblp_url)
            time.sleep(3)
            
            # 查找导出按钮
            try:
                # 查找"export records"相关的链接或按钮
                export_links = self.driver.find_elements(
                    By.XPATH, 
                    "//a[contains(text(), 'export') or contains(text(), 'Export')]"
                )
                
                if not export_links:
                    # 尝试查找包含"export"的链接
                    export_links = self.driver.find_elements(
                        By.XPATH,
                        "//a[contains(@href, 'export') or contains(@href, 'api')]"
                    )
                
                if export_links:
                    # 点击第一个导出链接
                    export_links[0].click()
                    time.sleep(2)
                    
                    # 查找JSON格式选项
                    json_links = self.driver.find_elements(
                        By.XPATH,
                        "//a[contains(text(), 'JSON') or contains(@href, 'format=json')]"
                    )
                    
                    if json_links:
                        json_url = json_links[0].get_attribute('href')
                        if json_url:
                            print(f"  访问JSON导出URL: {json_url}")
                            # 尝试直接用requests获取
                            try:
                                response = requests.get(json_url, timeout=30)
                                response.raise_for_status()
                                data = response.json()
                                if data:
                                    return data
                            except:
                                # 如果requests失败，使用selenium
                                self.driver.get(json_url)
                                time.sleep(2)
                                
                                page_source = self.driver.page_source
                                json_text = page_source.strip()
                                
                                # 清理可能的HTML
                                if json_text.startswith('<'):
                                    json_match = re.search(r'<pre[^>]*>(.*?)</pre>', json_text, re.DOTALL)
                                    if json_match:
                                        json_text = json_match.group(1)
                                
                                data = json.loads(json_text)
                                return data
            except (NoSuchElementException, TimeoutException) as e:
                print(f"  未找到导出按钮: {e}")
            
            # 如果以上方法都失败，返回None
            print(f"  无法获取JSON数据")
            return None
            
        except Exception as e:
            print(f"  下载JSON时出错: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def extract_papers_from_json(self, json_data: Dict[str, Any], 
                                 conference_abbr: str, year: int) -> List[Dict]:
        """
        从JSON数据中提取论文信息
        
        Args:
            json_data: DBLP返回的JSON数据
            conference_abbr: 会议简称
            year: 年份
            
        Returns:
            论文信息列表
        """
        papers = []
        
        if not json_data:
            return papers
        
        # DBLP JSON格式通常是 {"result": {"hits": {"hit": [...]}}}
        try:
            hits = json_data.get('result', {}).get('hits', {}).get('hit', [])
            
            # 如果hits是单个对象而不是列表
            if isinstance(hits, dict):
                hits = [hits]
            
            for hit in hits:
                info = hit.get('info', {})
                
                # 提取标题
                title = info.get('title', '')
                if isinstance(title, dict):
                    title = title.get('text', '') or title.get('', '')
                
                # 提取作者
                authors = []
                author_list = info.get('authors', {}).get('author', [])
                if isinstance(author_list, dict):
                    author_list = [author_list]
                
                for author in author_list:
                    if isinstance(author, dict):
                        author_name = author.get('text', '') or author.get('', '')
                        if author_name:
                            authors.append(author_name)
                
                # 如果标题和作者都存在，添加到列表
                if title:
                    papers.append({
                        'title': title,
                        'authors': '; '.join(authors) if authors else '',
                        'conference': conference_abbr,
                        'year': year
                    })
        
        except Exception as e:
            print(f"  解析JSON数据时出错: {e}")
            # 尝试备用解析方法
            try:
                # 直接查找所有可能的论文条目
                if 'result' in json_data:
                    result = json_data['result']
                    if 'hits' in result:
                        hits = result['hits']
                        if 'hit' in hits:
                            hit_list = hits['hit']
                            if isinstance(hit_list, list):
                                for hit in hit_list:
                                    if 'info' in hit:
                                        info = hit['info']
                                        title = info.get('title', '')
                                        if isinstance(title, dict):
                                            title = title.get('text', '') or title.get('', '')
                                        
                                        authors = []
                                        if 'authors' in info:
                                            authors_data = info['authors']
                                            if 'author' in authors_data:
                                                author_list = authors_data['author']
                                                if isinstance(author_list, list):
                                                    for author in author_list:
                                                        if isinstance(author, dict):
                                                            author_name = author.get('text', '') or author.get('', '')
                                                            if author_name:
                                                                authors.append(author_name)
                                                
                                                papers.append({
                                                    'title': title if title else '',
                                                    'authors': '; '.join(authors) if authors else '',
                                                    'conference': conference_abbr,
                                                    'year': year
                                                })
            except Exception as e2:
                print(f"  备用解析方法也失败: {e2}")
        
        return papers
    
    def process_conference(self, conference: Dict, year: int) -> None:
        """
        处理单个会议的所有URL
        
        Args:
            conference: 会议配置信息
            year: 年份
        """
        abbreviation = conference['abbreviation']
        dblp_urls = conference['dblp_urls']
        
        print(f"\n处理会议: {abbreviation} ({year}年)")
        
        for idx, url in enumerate(dblp_urls):
            # 如果是2024年，需要将URL中的2025替换为2024
            # 但如果是搜索URL（如MLSys），可能已经包含年份，不需要替换
            if year == 2024 and '2025' in url and 'search' not in url:
                url = url.replace('2025', '2024')
            
            print(f"  处理URL {idx + 1}/{len(dblp_urls)}: {url}")
            
            # 下载JSON数据
            json_data = self.download_json(url)
            
            if json_data:
                # 提取论文信息
                papers = self.extract_papers_from_json(json_data, abbreviation, year)
                print(f"  提取到 {len(papers)} 篇论文")
                self.papers.extend(papers)
            else:
                print(f"  未能获取数据")
            
            time.sleep(2)  # 避免请求过快
    
    def scrape_all(self, config_file: str = "conferences.json") -> None:
        """
        执行完整的爬取流程
        
        Args:
            config_file: 会议配置文件路径
        """
        conferences = self.load_conferences(config_file)
        
        print("=" * 60)
        print("开始论文信息搜集")
        print("=" * 60)
        
        for conference in conferences:
            abbreviation = conference['abbreviation']
            
            # 检查是否是特殊情况（MLSys只有2024年）
            if conference.get('only_2024', False):
                print(f"\n特殊处理: {abbreviation} 只有2024年")
                self.process_conference(conference, 2024)
                continue
            
            # 先处理2025年
            print(f"\n处理会议: {abbreviation}")
            print("  年份: 2025")
            self.process_conference(conference, 2025)
            
            # 再处理2024年
            print(f"\n处理会议: {abbreviation}")
            print("  年份: 2024")
            self.process_conference(conference, 2024)
        
        print("\n" + "=" * 60)
        print(f"爬取完成，共收集 {len(self.papers)} 篇论文")
        print("=" * 60)
    
    def save_to_csv(self, output_file: str = "papers.csv") -> None:
        """
        将论文信息保存为CSV文件
        
        Args:
            output_file: 输出文件名
        """
        if not self.papers:
            print("没有论文数据可保存")
            return
        
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            fieldnames = ['title', 'authors', 'conference', 'year']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            writer.writeheader()
            for paper in self.papers:
                writer.writerow(paper)
        
        print(f"\n论文信息已保存到: {output_file}")
        print(f"共 {len(self.papers)} 条记录")
    
    def close(self):
        """关闭浏览器"""
        if self.driver is not None:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None


def main():
    """主函数"""
    scraper = PaperScraper(headless=False)  # 设置为True可以无头模式运行
    
    try:
        # 执行爬取
        scraper.scrape_all()
        
        # 保存结果
        scraper.save_to_csv("papers.csv")
        
    except KeyboardInterrupt:
        print("\n\n用户中断程序")
    except Exception as e:
        print(f"\n\n程序出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()


if __name__ == "__main__":
    main()

