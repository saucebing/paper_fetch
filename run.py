#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速运行脚本
"""

from paper_scraper import PaperScraper

if __name__ == "__main__":
    # 创建爬虫实例
    # headless=True 表示无头模式（不显示浏览器窗口），False表示显示浏览器
    scraper = PaperScraper(headless=False)
    
    try:
        # 执行爬取
        scraper.scrape_all("conferences.json")
        
        # 保存结果
        scraper.save_to_csv("papers.csv")
        
        print("\n✅ 所有任务完成！")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断程序")
        # 即使中断，也保存已收集的数据
        if scraper.papers:
            scraper.save_to_csv("papers_partial.csv")
            print("已保存部分数据到 papers_partial.csv")
    except Exception as e:
        print(f"\n\n❌ 程序出错: {e}")
        import traceback
        traceback.print_exc()
        # 即使出错，也保存已收集的数据
        if scraper.papers:
            scraper.save_to_csv("papers_partial.csv")
            print("已保存部分数据到 papers_partial.csv")
    finally:
        scraper.close()

