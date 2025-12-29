#!/bin/bash
# 论文信息搜集工具使用示例

echo "=== 示例1: 只处理前1个会议，每个会议前5篇论文（用于测试）==="
python run.py --max-conferences 1 --max-papers 5 --output test_papers.csv

echo ""
echo "=== 示例2: 只处理前3个会议，每个会议前10篇论文 ==="
# python run.py --max-conferences 3 --max-papers 10

echo ""
echo "=== 示例3: 处理所有会议，但每个会议只处理前20篇论文 ==="
# python run.py --max-papers 20

echo ""
echo "=== 示例4: 处理所有数据（完整运行）==="
# python run.py
