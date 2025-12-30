#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用Semantic Scholar API为论文添加abstract和引用量
"""

import csv
import time
import requests
from typing import Dict, Any, Optional
import urllib.parse


class SemanticScholarEnricher:
    def __init__(self, api_key: str, get_affiliations: bool = True, max_authors_for_affiliations: int = None):
        """
        初始化Semantic Scholar API客户端
        
        Args:
            api_key: Semantic Scholar API密钥
            get_affiliations: 是否获取作者单位信息（会增加API调用次数和处理时间）
            max_authors_for_affiliations: 最多获取前n个作者的单位（None表示获取所有作者的单位）
        """
        self.api_key = api_key
        self.base_url = "https://api.semanticscholar.org/graph/v1"
        self.headers = {
            'x-api-key': api_key,
            'Accept': 'application/json'
        }
        self.last_request_time = 0  # 用于控制请求频率
        self.get_affiliations = get_affiliations  # 是否获取单位信息
        self.max_authors_for_affiliations = max_authors_for_affiliations  # 最多获取前n个作者的单位
        
    def _wait_for_rate_limit(self):
        """等待以满足频率限制（1请求/秒）"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < 1.1:  # 稍微多等一点，确保不会超限
            wait_time = 1.1 - time_since_last_request
            time.sleep(wait_time)
        self.last_request_time = time.time()
    
    def search_paper(self, title: str, authors: str = None, year: int = None) -> Optional[Dict[str, Any]]:
        """
        根据标题和作者搜索论文
        
        Args:
            title: 论文标题
            authors: 作者列表（可选）
            year: 年份（可选）
            
        Returns:
            论文信息字典，如果未找到返回None
        """
        self._wait_for_rate_limit()
        
        # 构建搜索查询
        # 使用标题作为主要搜索词
        query = title
        
        # 如果提供了作者，可以添加到查询中（但Semantic Scholar的搜索API可能不支持作者参数）
        # 我们先用标题搜索，然后过滤结果
        
        try:
            # 清理查询字符串（移除特殊字符，限制长度）
            # 移除末尾的标点符号
            query = query.rstrip('.,;:!?')
            # 如果查询太长，截取前200个字符
            if len(query) > 200:
                query = query[:200]
            
            # 使用搜索API
            search_url = f"{self.base_url}/paper/search"
            params = {
                'query': query,
                'limit': 10  # 获取前10个结果，然后匹配最合适的
            }
            
            # 注意：year参数可能在某些情况下会导致400错误，先不使用
            # if year:
            #     params['year'] = year
            
            response = requests.get(search_url, headers=self.headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                papers = data.get('data', [])
                
                if not papers:
                    return None
                
                # 尝试找到最匹配的论文
                # 比较标题相似度
                best_match = None
                best_score = 0
                
                title_lower = title.lower().strip()
                
                for paper in papers:
                    paper_title = paper.get('title', '').lower().strip()
                    
                    # 计算标题相似度（简单方法：检查是否包含或相似）
                    if title_lower == paper_title:
                        # 完全匹配
                        best_match = paper
                        break
                    elif title_lower in paper_title or paper_title in title_lower:
                        # 部分匹配
                        score = min(len(title_lower), len(paper_title)) / max(len(title_lower), len(paper_title))
                        if score > best_score:
                            best_score = score
                            best_match = paper
                
                # 如果找到了匹配的论文，获取详细信息
                if best_match:
                    paper_id = best_match.get('paperId')
                    if paper_id:
                        # 确保满足频率限制后再调用
                        self._wait_for_rate_limit()
                        return self.get_paper_details(paper_id, get_affiliations=self.get_affiliations)
                
                # 如果没有找到匹配的，返回第一个结果
                if papers:
                    paper_id = papers[0].get('paperId')
                    if paper_id:
                        # 确保满足频率限制后再调用
                        self._wait_for_rate_limit()
                        return self.get_paper_details(paper_id, get_affiliations=self.get_affiliations)
            
            elif response.status_code == 429:
                print(f"  遇到速率限制，等待更长时间...")
                time.sleep(5)
                return None
            else:
                print(f"  搜索API返回错误: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"  请求错误: {e}")
            return None
        except Exception as e:
            print(f"  搜索时出错: {e}")
            return None
        
        return None
    
    def get_author_affiliations(self, author_id: str) -> list:
        """
        获取作者的单位信息
        
        Args:
            author_id: Semantic Scholar作者ID
            
        Returns:
            单位列表
        """
        self._wait_for_rate_limit()
        
        try:
            url = f"{self.base_url}/author/{author_id}"
            params = {
                'fields': 'affiliations'
            }
            
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('affiliations', [])
            elif response.status_code == 429:
                print(f"  遇到速率限制，等待更长时间...")
                time.sleep(5)
                return []
            else:
                return []
                
        except Exception as e:
            return []
    
    def get_paper_details(self, paper_id: str, get_affiliations: bool = False) -> Optional[Dict[str, Any]]:
        """
        根据论文ID获取详细信息（包括abstract和citationCount）
        
        Args:
            paper_id: Semantic Scholar论文ID
            get_affiliations: 是否获取作者单位信息（会增加API调用次数）
            
        Returns:
            论文详细信息字典，如果get_affiliations=True，会包含authorsWithAffiliations字段
        """
        self._wait_for_rate_limit()
        
        try:
            url = f"{self.base_url}/paper/{paper_id}"
            params = {
                'fields': 'abstract,citationCount,title,authors,year'
            }
            
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            
            if response.status_code == 200:
                paper_data = response.json()
                
                # 如果需要获取单位信息
                if get_affiliations and 'authors' in paper_data:
                    authors_with_affiliations = []
                    authors_list = paper_data.get('authors', [])
                    
                    # 确定要获取单位的作者数量
                    if self.max_authors_for_affiliations is not None:
                        authors_to_process = min(self.max_authors_for_affiliations, len(authors_list))
                    else:
                        authors_to_process = len(authors_list)
                    
                    for idx, author in enumerate(authors_list):
                        author_id = author.get('authorId')
                        author_name = author.get('name', '')
                        
                        # 只获取前n个作者的单位
                        if idx < authors_to_process:
                            if author_id:
                                affiliations = self.get_author_affiliations(author_id)
                                authors_with_affiliations.append({
                                    'name': author_name,
                                    'affiliations': affiliations,
                                    'has_affiliations': True
                                })
                            else:
                                authors_with_affiliations.append({
                                    'name': author_name,
                                    'affiliations': [],
                                    'has_affiliations': True
                                })
                        else:
                            # 后面的作者不获取单位，只记录名字
                            authors_with_affiliations.append({
                                'name': author_name,
                                'affiliations': [],
                                'has_affiliations': False
                            })
                    
                    paper_data['authorsWithAffiliations'] = authors_with_affiliations
                
                return paper_data
            elif response.status_code == 429:
                print(f"  遇到速率限制，等待更长时间...")
                time.sleep(5)
                return None
            else:
                print(f"  获取论文详情失败: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"  请求错误: {e}")
            return None
        except Exception as e:
            print(f"  获取论文详情时出错: {e}")
            return None
    
    def enrich_paper(self, title: str, authors: str = None, year: int = None) -> Dict[str, Any]:
        """
        为单篇论文获取abstract和引用量
        
        Args:
            title: 论文标题
            authors: 作者列表（可选）
            year: 年份（可选）
            
        Returns:
            包含abstract、citationCount和affiliations的字典
        """
        result = {
            'abstract': '',
            'citationCount': 0,
            'affiliations': ''  # 作者单位信息（格式：作者1: 单位1; 单位2 | 作者2: 单位1）
        }
        
        # 搜索论文
        paper_info = self.search_paper(title, authors, year)
        
        if paper_info:
            # 确保abstract始终是字符串，不会是None
            abstract = paper_info.get('abstract', '')
            result['abstract'] = abstract if abstract is not None else ''
            
            # 确保citationCount始终是整数
            citation_count = paper_info.get('citationCount', 0)
            result['citationCount'] = int(citation_count) if citation_count is not None else 0
            
            # 如果获取了作者单位信息
            if 'authorsWithAffiliations' in paper_info:
                affiliations_list = []
                for author_info in paper_info['authorsWithAffiliations']:
                    author_name = author_info.get('name', '')
                    affiliations = author_info.get('affiliations', [])
                    has_affiliations = author_info.get('has_affiliations', True)
                    
                    if has_affiliations:
                        # 如果尝试获取了单位信息
                        if affiliations:
                            # 格式：作者名: 单位1; 单位2
                            aff_str = f"{author_name}: {'; '.join(affiliations)}"
                        else:
                            # 如果没有单位，显示(无)
                            aff_str = f"{author_name}: (无)"
                    else:
                        # 如果没有获取单位信息（后面的作者），只显示名字
                        aff_str = author_name
                    
                    affiliations_list.append(aff_str)
                
                # 用 | 分隔不同作者
                result['affiliations'] = ' | '.join(affiliations_list)
        
        return result
    
    def _save_progress(self, papers: list, output_file: str):
        """保存当前进度"""
        fieldnames = ['title', 'authors', 'conference', 'year', 'abstract', 'citationCount', 'affiliations']
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for paper in papers:
                # 确保citationCount是整数类型
                citation_count = paper.get('citationCount', 0)
                try:
                    if isinstance(citation_count, str):
                        citation_count = int(citation_count.strip()) if citation_count.strip() else 0
                    else:
                        citation_count = int(citation_count) if citation_count else 0
                except (ValueError, TypeError):
                    citation_count = 0
                
                writer.writerow({
                    'title': paper.get('title', ''),
                    'authors': paper.get('authors', ''),
                    'conference': paper.get('conference', ''),
                    'year': paper.get('year', ''),
                    'abstract': paper.get('abstract', ''),
                    'citationCount': citation_count,
                    'affiliations': paper.get('affiliations', '')
                })
    
    def enrich_csv(self, input_file: str, output_file: str, start_from: int = 0, max_papers: int = None, skip_existing_abstract: bool = False):
        """
        为CSV文件中的所有论文添加abstract和引用量
        
        Args:
            input_file: 输入CSV文件路径
            output_file: 输出CSV文件路径
            start_from: 从第几行开始处理（用于断点续传）
            max_papers: 最多处理的论文数量（None表示处理所有）
            skip_existing_abstract: 如果为True，跳过已有abstract的行，直接复制到输出
        """
        print("=" * 60)
        print("开始使用Semantic Scholar API丰富论文信息")
        if start_from > 0:
            print(f"从第 {start_from + 1} 行开始处理（断点续传）")
        if max_papers:
            print(f"限制处理前 {max_papers} 篇论文")
        if skip_existing_abstract:
            print("跳过已有abstract的行（直接复制）")
        print("=" * 60)
        
        # 读取输入CSV（处理可能的BOM）
        papers = []
        with open(input_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            papers = list(reader)
        
        total = len(papers)
        
        # 如果设置了max_papers，限制处理范围
        if max_papers:
            end_idx = min(start_from + max_papers, total)
            papers_to_process = end_idx - start_from
            print(f"共 {total} 篇论文，将处理 {papers_to_process} 篇（从第 {start_from + 1} 行到第 {end_idx} 行）")
        else:
            end_idx = total
            papers_to_process = total - start_from
            print(f"共 {total} 篇论文需要处理")
            if start_from > 0:
                print(f"已处理 {start_from} 篇，剩余 {papers_to_process} 篇")
        print()
        
        # 初始化abstract、citationCount和affiliations字段（如果不存在），并确保类型正确
        for paper in papers:
            if 'abstract' not in paper:
                paper['abstract'] = ''
            if 'citationCount' not in paper:
                paper['citationCount'] = 0
            else:
                # 确保citationCount是整数类型（CSV读取的是字符串）
                try:
                    citation_count = paper.get('citationCount', 0)
                    if isinstance(citation_count, str):
                        # 如果是字符串，尝试转换为整数
                        citation_count = citation_count.strip()
                        paper['citationCount'] = int(citation_count) if citation_count else 0
                    elif citation_count is None or citation_count == '':
                        paper['citationCount'] = 0
                    else:
                        paper['citationCount'] = int(citation_count)
                except (ValueError, TypeError):
                    # 如果转换失败，设为0
                    paper['citationCount'] = 0
            if 'affiliations' not in paper:
                paper['affiliations'] = ''
        
        # 处理每篇论文
        # 确保citationCount是整数类型后再比较
        def has_data(paper):
            abstract = paper.get('abstract', '').strip()
            citation_count = paper.get('citationCount', 0)
            try:
                if isinstance(citation_count, str):
                    citation_count = int(citation_count.strip()) if citation_count.strip() else 0
                else:
                    citation_count = int(citation_count) if citation_count else 0
            except (ValueError, TypeError):
                citation_count = 0
            return bool(abstract) or citation_count > 0
        
        success_count = sum(1 for p in papers[:start_from] if has_data(p))
        failed_count = start_from - success_count
        skipped_count = 0  # 统计跳过的数量
        
        try:
            for idx in range(start_from, end_idx):
                paper = papers[idx]
                title = paper.get('title', '').strip()
                authors = paper.get('authors', '').strip()
                year_str = paper.get('year', '').strip()
                conference = paper.get('conference', '').strip()
                
                # 如果启用了skip_existing_abstract选项，检查abstract字段
                if skip_existing_abstract:
                    existing_abstract = paper.get('abstract', '').strip()
                    if existing_abstract:
                        # abstract不为空，跳过处理，直接复制
                        print(f"[{idx+1}/{total}] 跳过（已有abstract）: {title[:60]}...")
                        skipped_count += 1
                        continue
                
                # 如果已经有数据，跳过（但如果没有单位信息且需要获取，则继续处理）
                # 确保citationCount是整数类型后再比较
                citation_count = paper.get('citationCount', 0)
                try:
                    if isinstance(citation_count, str):
                        citation_count = int(citation_count.strip()) if citation_count.strip() else 0
                    else:
                        citation_count = int(citation_count) if citation_count else 0
                except (ValueError, TypeError):
                    citation_count = 0
                
                has_data = bool(paper.get('abstract', '').strip()) or citation_count > 0
                has_affiliations = paper.get('affiliations', '')
                if has_data and (not self.get_affiliations or has_affiliations):
                    print(f"[{idx+1}/{total}] 跳过（已有数据）: {title[:60]}...")
                    skipped_count += 1
                    continue
                
                # 解析年份
                year = None
                if year_str:
                    try:
                        year = int(year_str)
                    except:
                        pass
                
                print(f"[{idx+1}/{total}] 处理: {title[:60]}...")
                print(f"  会议: {conference}, 年份: {year}")
                
                # 获取abstract、引用量和单位信息
                try:
                    result = self.enrich_paper(title, authors, year)
                    
                    # 确保abstract是字符串，不会是None
                    abstract = result.get('abstract', '') or ''
                    citation_count = result.get('citationCount', 0) or 0
                    
                    if abstract or citation_count > 0:
                        paper['abstract'] = abstract
                        paper['citationCount'] = citation_count
                        paper['affiliations'] = result.get('affiliations', '') or ''
                        success_count += 1
                        
                        # 确保affiliations是字符串，避免NoneType错误
                        affiliations = result.get('affiliations', '') or ''
                        aff_info = f", 单位信息: {len(affiliations)} 字符" if affiliations else ""
                        print(f"  ✓ 成功获取 - 引用量: {citation_count}, Abstract长度: {len(abstract)}{aff_info}")
                    else:
                        paper['abstract'] = ''
                        paper['citationCount'] = 0
                        paper['affiliations'] = ''
                        failed_count += 1
                        print(f"  ✗ 未找到匹配的论文")
                except Exception as e:
                    paper['abstract'] = ''
                    paper['citationCount'] = 0
                    paper['affiliations'] = ''
                    failed_count += 1
                    print(f"  ✗ 处理出错: {e}")
                
                # 每50篇保存一次进度
                if (idx + 1) % 50 == 0:
                    self._save_progress(papers, output_file)
                    print(f"\n  [已保存进度] 成功 {success_count}, 失败 {failed_count}, 完成率 {(idx+1)*100//end_idx}%\n")
                
                # 每100篇显示一次进度统计
                if (idx + 1) % 100 == 0:
                    print(f"\n进度统计: 成功 {success_count}, 失败 {failed_count}, 完成率 {(idx+1)*100//end_idx}%\n")
                
                # 如果是最后一篇，确保保存
                if idx + 1 == end_idx:
                    self._save_progress(papers, output_file)
                    print(f"\n  [已保存进度] 处理完最后一篇，已保存所有结果\n")
                
                print()  # 空行分隔
        
        except KeyboardInterrupt:
            print("\n\n用户中断程序，保存当前进度...")
            self._save_progress(papers, output_file)
            print(f"已保存进度到: {output_file}")
            print(f"已处理: {idx+1}/{end_idx} 篇")
            return
        
        # 保存最终结果（确保保存）
        self._save_progress(papers, output_file)
        
        print("=" * 60)
        print(f"处理完成！")
        print(f"成功: {success_count}/{papers_to_process} ({success_count*100//papers_to_process if papers_to_process > 0 else 0}%)")
        print(f"失败: {failed_count}/{papers_to_process}")
        if skip_existing_abstract and skipped_count > 0:
            print(f"跳过: {skipped_count}/{papers_to_process} (已有abstract)")
        print("=" * 60)
        print(f"\n结果已保存到: {output_file}")


def main():
    """主函数"""
    API_KEY = "F2UHMkH5fb4EuF0DdWjAo4CU9PKE4yns5lbYJv21"
    
    # 默认获取单位信息，可以通过参数控制
    enricher = SemanticScholarEnricher(API_KEY, get_affiliations=True, max_authors_for_affiliations=None)
    
    try:
        enricher.enrich_csv("papers.csv", "papers_enriched.csv")
    except KeyboardInterrupt:
        print("\n\n用户中断程序")
    except Exception as e:
        print(f"\n\n程序出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

