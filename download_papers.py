#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
论文PDF下载工具
使用Selenium从会议网站下载论文PDF

使用方法:
    python download_papers.py
"""

import json
import time
import random
import re
import os
import urllib.parse
from typing import List, Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import requests


class PaperDownloader:
    def __init__(self, download_dir: str = "./downloads"):
        """
        初始化下载器
        
        Args:
            download_dir: PDF下载目录
        """
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
        self.driver = None
        
    def _init_driver(self):
        """初始化Selenium WebDriver"""
        if self.driver is not None:
            return
        
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--user-data-dir=/tmp/chrome-data")
        
        # 设置下载目录
        prefs = {
            "download.default_directory": os.path.abspath(self.download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        options.add_experimental_option("prefs", prefs)
        
        # 尝试找到Chrome二进制文件
        chrome_paths = [
            "/root/chrome-linux64/chrome",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
            "/usr/bin/chrome",
        ]
        
        for path in chrome_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                options.binary_location = path
                print(f"使用Chrome二进制: {path}")
                break
        
        try:
            self.driver = webdriver.Chrome(options=options)
            self.driver.implicitly_wait(10)
            print("Selenium WebDriver初始化成功")
        except Exception as e:
            print(f"Selenium WebDriver初始化失败: {e}")
            raise
    
    def _random_delay(self, min_seconds: float = 3.0, max_seconds: float = 6.0):
        """
        随机延迟，避免被识别为爬虫
        
        Args:
            min_seconds: 最小延迟秒数
            max_seconds: 最大延迟秒数
        """
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        清理文件名，移除非法字符
        
        Args:
            filename: 原始文件名
            
        Returns:
            清理后的文件名
        """
        # 替换空格为下划线
        filename = filename.replace(' ', '_')
        # 移除或替换非法字符
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # 移除连续的下划线
        filename = re.sub(r'_+', '_', filename)
        # 移除首尾下划线
        filename = filename.strip('_')
        # 限制长度
        if len(filename) > 200:
            filename = filename[:200]
        return filename
    
    def _find_pdf_link(self, page_source: str) -> Optional[str]:
        """
        在页面源码中查找PDF链接
        
        Args:
            page_source: 页面HTML源码
            
        Returns:
            PDF链接，如果未找到返回None
        """
        # 查找所有PDF链接
        pdf_patterns = [
            r'https?://[^\s"\'<>]+\.pdf',
            r'href=["\']([^"\']+\.pdf)["\']',
            r'<a[^>]+href=["\']([^"\']+\.pdf)["\'][^>]*>',
        ]
        
        for pattern in pdf_patterns:
            matches = re.findall(pattern, page_source, re.IGNORECASE)
            if matches:
                # 返回第一个匹配的链接
                pdf_url = matches[0]
                # 如果是相对路径，需要转换为绝对路径
                if pdf_url.startswith('//'):
                    pdf_url = 'https:' + pdf_url
                elif pdf_url.startswith('/'):
                    # 需要从当前页面URL获取基础URL
                    current_url = self.driver.current_url
                    base_url = '/'.join(current_url.split('/')[:3])
                    pdf_url = base_url + pdf_url
                return pdf_url
        
        return None
    
    def _download_pdf(self, pdf_url: str, save_path: str) -> bool:
        """
        下载PDF文件
        
        Args:
            pdf_url: PDF文件URL
            save_path: 保存路径
            
        Returns:
            是否下载成功
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(pdf_url, headers=headers, timeout=30, stream=True)
            response.raise_for_status()
            
            # 检查Content-Type是否为PDF
            content_type = response.headers.get('Content-Type', '')
            if 'pdf' not in content_type.lower() and not pdf_url.lower().endswith('.pdf'):
                print(f"  警告: 响应类型不是PDF: {content_type}")
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # 检查文件大小
            file_size = os.path.getsize(save_path)
            if file_size < 1000:  # 小于1KB可能是错误页面
                os.remove(save_path)
                print(f"  警告: 下载的文件太小({file_size}字节)，可能不是有效的PDF")
                return False
            
            return True
        except Exception as e:
            print(f"  下载PDF失败: {e}")
            if os.path.exists(save_path):
                os.remove(save_path)
            return False
    
    def _get_paper_title_from_page(self) -> Optional[str]:
        """
        从论文详情页获取论文标题
        
        Returns:
            论文标题，如果未找到返回None
        """
        try:
            # 尝试多种方式查找标题
            title_selectors = [
                "h1",
                "h2",
                ".paper-title",
                ".title",
                "[class*='title']",
                "[class*='Title']",
            ]
            
            for selector in title_selectors:
                try:
                    title_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    title = title_elem.text.strip()
                    if title and len(title) > 10:  # 标题应该有一定长度
                        return title
                except NoSuchElementException:
                    continue
            
            # 如果都找不到，尝试从页面标题获取
            page_title = self.driver.title
            if page_title:
                # 移除常见的后缀
                page_title = re.sub(r'\s*[-|]\s*.*$', '', page_title)
                return page_title.strip()
            
            return None
        except Exception as e:
            print(f"  获取论文标题失败: {e}")
            return None
    
    def _process_paper_detail_page(self, paper_url: str, conference_abbr: str, year: int) -> bool:
        """
        处理单篇论文详情页，下载PDF
        
        Args:
            paper_url: 论文详情页URL
            conference_abbr: 会议简称
            year: 年份
            
        Returns:
            是否成功下载
        """
        try:
            print(f"    访问论文详情页: {paper_url}")
            self.driver.get(paper_url)
            self._random_delay(3, 5)
            
            # 获取论文标题
            paper_title = self._get_paper_title_from_page()
            if not paper_title:
                print(f"    警告: 无法获取论文标题，使用URL作为标题")
                # 从URL提取标题
                paper_title = urllib.parse.unquote(paper_url.split('/')[-1])
            
            # 清理标题
            paper_title = self._sanitize_filename(paper_title)
            
            # 查找PDF链接
            page_source = self.driver.page_source
            pdf_url = self._find_pdf_link(page_source)
            
            if not pdf_url:
                print(f"    ✗ 未找到PDF链接: {paper_title[:60]}...")
                return False
            
            print(f"    找到PDF链接: {pdf_url}")
            
            # 生成保存路径
            filename = f"{conference_abbr}_{year}_{paper_title}.pdf"
            save_path = os.path.join(self.download_dir, filename)
            
            # 如果文件已存在，跳过
            if os.path.exists(save_path):
                print(f"    ⏭ 文件已存在，跳过: {filename}")
                return True
            
            # 下载PDF
            print(f"    下载PDF: {filename}")
            self._random_delay(2, 4)
            
            if self._download_pdf(pdf_url, save_path):
                print(f"    ✓ 下载成功: {filename}")
                return True
            else:
                print(f"    ✗ 下载失败: {filename}")
                return False
                
        except Exception as e:
            print(f"    处理论文详情页出错: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _process_conference_page(self, dblp_url: str, conference_abbr: str, year: int, max_papers: int = None) -> int:
        """
        处理会议页面，找到所有论文并下载
        
        Args:
            dblp_url: DBLP会议页面URL
            conference_abbr: 会议简称
            year: 年份
            max_papers: 最多处理的论文数量（None表示处理所有）
            
        Returns:
            成功下载的论文数量
        """
        print(f"\n处理会议: {conference_abbr} ({year}年)")
        print(f"URL: {dblp_url}")
        
        try:
            self.driver.get(dblp_url)
            self._random_delay(4, 6)
            
            # 查找所有view按钮/链接
            # 通常view链接包含"presentation"、"paper"、"view"等关键词
            view_links = []
            
            # 等待页面加载
            time.sleep(2)
            
            # 尝试多种方式查找view链接
            try:
                # 方法1: 查找包含"view"、"View"、"presentation"等关键词的链接文本
                view_texts = ['view', 'View', 'VIEW', 'presentation', 'Presentation', 'paper', 'Paper']
                for text in view_texts:
                    try:
                        elements = self.driver.find_elements(
                            By.XPATH,
                            f"//a[contains(text(), '{text}') or contains(@href, '{text.lower()}')]"
                        )
                        for elem in elements:
                            href = elem.get_attribute('href')
                            if href and href not in view_links:
                                # 检查是否是论文详情页链接
                                if any(keyword in href.lower() for keyword in ['presentation', 'paper', 'view', 'detail', 'abstract']):
                                    view_links.append(href)
                    except:
                        continue
                
            except Exception as e:
                print(f"  查找view链接时出错: {e}")
            
            # 方法2: 如果没找到，尝试查找所有链接，然后过滤
            if not view_links:
                try:
                    all_links = self.driver.find_elements(By.TAG_NAME, "a")
                    for link in all_links:
                        href = link.get_attribute('href')
                        link_text = link.text.strip().lower()
                        
                        if href:
                            # 检查链接是否包含论文相关的关键词
                            href_lower = href.lower()
                            if any(keyword in href_lower for keyword in ['presentation', 'paper', 'view', 'detail']):
                                if href not in view_links:
                                    view_links.append(href)
                            # 或者链接文本包含view等关键词
                            elif any(keyword in link_text for keyword in ['view', 'presentation', 'paper']) and 'http' in href:
                                if href not in view_links:
                                    view_links.append(href)
                except Exception as e:
                    print(f"  查找所有链接时出错: {e}")
            
            # 方法3: 尝试从DBLP页面直接提取论文链接
            # DBLP页面通常有论文列表，链接可能指向会议网站
            if not view_links:
                try:
                    # 查找包含会议名称或年份的链接
                    page_source = self.driver.page_source
                    # 使用正则表达式查找可能的论文链接
                    link_pattern = r'href=["\']([^"\']*(?:presentation|paper|view|detail)[^"\']*)["\']'
                    matches = re.findall(link_pattern, page_source, re.IGNORECASE)
                    for match in matches:
                        if match.startswith('http') and match not in view_links:
                            view_links.append(match)
                except Exception as e:
                    print(f"  从页面源码提取链接时出错: {e}")
            
            # 去重
            view_links = list(set(view_links))
            
            if not view_links:
                print(f"  警告: 未找到任何论文链接")
                return 0
            
            print(f"  找到 {len(view_links)} 个论文链接")
            
            # 跳过第一篇（通常是致辞），从第二篇开始
            papers_to_process = view_links[1:] if len(view_links) > 1 else view_links
            
            # 如果设置了max_papers，限制处理数量
            if max_papers and len(papers_to_process) > max_papers:
                papers_to_process = papers_to_process[:max_papers]
                print(f"  限制处理前 {max_papers} 篇论文（跳过第一篇致辞）")
            else:
                print(f"  将处理 {len(papers_to_process)} 篇论文（跳过第一篇致辞）")
            
            success_count = 0
            total_papers = len(view_links) - 1  # 减去致辞
            for idx, paper_url in enumerate(papers_to_process, 2):  # 从2开始计数
                print(f"\n  [{idx}/{len(view_links)}] 处理论文 {idx}")
                if self._process_paper_detail_page(paper_url, conference_abbr, year):
                    success_count += 1
                
                # 每篇论文之间延迟
                if idx < len(view_links) and (not max_papers or idx - 1 < max_papers):
                    self._random_delay(3, 6)
            
            print(f"\n  完成！成功下载 {success_count}/{len(papers_to_process)} 篇论文")
            return success_count
            
        except Exception as e:
            print(f"  处理会议页面出错: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    def load_conferences(self, config_file: str = "conferences.json") -> List[Dict]:
        """加载会议配置"""
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def download_all(self, config_file: str = "conferences.json", max_conferences: int = None, max_papers_per_conference: int = None):
        """
        下载所有会议的论文PDF
        
        Args:
            config_file: 会议配置文件路径
            max_conferences: 最多处理的会议数量（None表示处理所有）
            max_papers_per_conference: 每个会议最多处理的论文数量（None表示处理所有）
        """
        print("=" * 60)
        print("开始下载论文PDF")
        if max_conferences:
            print(f"限制处理前 {max_conferences} 个会议")
        if max_papers_per_conference:
            print(f"每个会议最多处理 {max_papers_per_conference} 篇论文")
        print("=" * 60)
        
        # 初始化WebDriver
        self._init_driver()
        
        try:
            conferences = self.load_conferences(config_file)
            
            # 如果设置了max_conferences，限制处理数量
            if max_conferences and len(conferences) > max_conferences:
                conferences = conferences[:max_conferences]
                print(f"限制处理前 {max_conferences} 个会议\n")
            
            for conference in conferences:
                abbreviation = conference['abbreviation']
                dblp_urls = conference['dblp_urls']
                
                # 检查是否是特殊情况（MLSys只有2024年）
                if conference.get('only_2024', False):
                    print(f"\n特殊处理: {abbreviation} 只有2024年")
                    for url in dblp_urls:
                        self._process_conference_page(url, abbreviation, 2024, max_papers=max_papers_per_conference)
                        self._random_delay(5, 8)
                    continue
                
                # 先处理2025年
                print(f"\n处理会议: {abbreviation}")
                print("  年份: 2025")
                
                for url_idx, url in enumerate(dblp_urls, 1):
                    print(f"\n  处理URL {url_idx}/{len(dblp_urls)}")
                    self._process_conference_page(url, abbreviation, 2025, max_papers=max_papers_per_conference)
                    
                    # URL之间的延迟
                    if url_idx < len(dblp_urls):
                        self._random_delay(5, 8)
                
                # 再处理2024年
                print(f"\n处理会议: {abbreviation}")
                print("  年份: 2024")
                
                for url_idx, url in enumerate(dblp_urls, 1):
                    # 将URL中的2025替换为2024
                    url_2024 = url.replace('2025', '2024')
                    print(f"\n  处理URL {url_idx}/{len(dblp_urls)}")
                    self._process_conference_page(url_2024, abbreviation, 2024, max_papers=max_papers_per_conference)
                    
                    # URL之间的延迟
                    if url_idx < len(dblp_urls):
                        self._random_delay(5, 8)
            
            print("\n" + "=" * 60)
            print("所有论文下载完成！")
            print("=" * 60)
            
        except KeyboardInterrupt:
            print("\n\n用户中断程序")
        except Exception as e:
            print(f"\n\n程序出错: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.close()
    
    def close(self):
        """关闭浏览器"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='论文PDF下载工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python download_papers.py                              # 下载所有论文
  python download_papers.py --max-conferences 3          # 只处理前3个会议
  python download_papers.py --max-papers 10              # 每个会议只处理10篇论文
  python download_papers.py --max-conferences 2 --max-papers 5  # 前2个会议，每个5篇
        """
    )
    parser.add_argument('--max-conferences', type=int, default=None,
                       help='最多处理的会议数量（默认：处理所有）')
    parser.add_argument('--max-papers', type=int, default=None,
                       help='每个会议最多处理的论文数量（默认：处理所有）')
    parser.add_argument('--config', type=str, default='conferences.json',
                       help='会议配置文件路径（默认：conferences.json）')
    parser.add_argument('--download-dir', type=str, default='./downloads',
                       help='PDF下载目录（默认：./downloads）')
    
    args = parser.parse_args()
    
    downloader = PaperDownloader(download_dir=args.download_dir)
    
    try:
        downloader.download_all(
            config_file=args.config,
            max_conferences=args.max_conferences,
            max_papers_per_conference=args.max_papers
        )
    except Exception as e:
        print(f"程序出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        downloader.close()


if __name__ == "__main__":
    main()

