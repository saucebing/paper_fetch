#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速运行脚本 - 使用Semantic Scholar API丰富论文信息
"""

from enrich_with_semantic_scholar import SemanticScholarEnricher
import sys
import argparse

def main():
    API_KEY = "F2UHMkH5fb4EuF0DdWjAo4CU9PKE4yns5lbYJv21"
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description='使用Semantic Scholar API丰富论文信息',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_enrich.py                    # 处理所有论文
  python run_enrich.py --max-papers 100    # 只处理前100篇
  python run_enrich.py --start-from 1000   # 从第1000行开始处理
  python run_enrich.py --start-from 1000 --max-papers 50  # 从第1000行开始，处理50篇
        """
    )
    parser.add_argument('--start-from', type=int, default=0,
                       help='从第几行开始处理（用于断点续传，默认：0）')
    parser.add_argument('--max-papers', type=int, default=None,
                       help='最多处理的论文数量（默认：处理所有）')
    parser.add_argument('--input', type=str, default='papers.csv',
                       help='输入CSV文件路径（默认：papers.csv）')
    parser.add_argument('--output', type=str, default='papers_enriched.csv',
                       help='输出CSV文件路径（默认：papers_enriched.csv）')
    
    args = parser.parse_args()
    
    enricher = SemanticScholarEnricher(API_KEY)
    
    try:
        enricher.enrich_csv(
            args.input, 
            args.output, 
            start_from=args.start_from,
            max_papers=args.max_papers
        )
        print("\n✅ 所有任务完成！")
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断程序")
        print(f"已保存当前进度到 {args.output}")
    except Exception as e:
        print(f"\n\n❌ 程序出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

