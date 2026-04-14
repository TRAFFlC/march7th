#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
from emotion_classifier import LLMEmotionClassifier


def main():
    parser = argparse.ArgumentParser(
        description="情绪分类文本工具 - 对多行文本进行情绪分类"
    )
    parser.add_argument("input_file", type=str, help="输入文本文件路径")
    parser.add_argument(
        "-o", "--output", type=str, default=None, help="输出文件路径（可选）"
    )
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"错误: 输入文件不存在: {input_path}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_suffix(".labeled" + input_path.suffix)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"正在初始化情绪分类器...")
    classifier = LLMEmotionClassifier()

    print(f"正在读取文件: {input_path}")
    lines = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            lines.append(line.rstrip("\n\r"))

    print(f"共 {len(lines)} 行，开始分类...")
    results = []
    for i, line in enumerate(lines, 1):
        if line.strip():
            emotion = classifier.predict(line)
            results.append(f"{line} [EMOTION: {emotion}]")
        else:
            results.append(line)
        if i % 10 == 0:
            print(f"已处理 {i}/{len(lines)} 行...")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(results))
        if results:
            f.write("\n")

    print(f"分类完成! 结果已保存到: {output_path}")


if __name__ == "__main__":
    main()
