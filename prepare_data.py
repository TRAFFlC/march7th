"""
准备三月七角色扮演训练数据
"""
import json
from pathlib import Path
from typing import List, Dict

DATA_DIR = Path(__file__).parent / "march7th_typical_lines"
OUTPUT_DIR = Path(__file__).parent / "data"


def load_jsonl(file_path: Path) -> List[Dict]:
    data = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return data


def load_all_data() -> List[Dict]:
    all_data = []

    training_file = DATA_DIR.parent / "training_data.txt"
    if training_file.exists():
        data = load_jsonl(training_file)
        all_data.extend(data)
        print(f"加载 {training_file.name}: {len(data)} 条")

    return all_data


def validate_data(data: List[Dict]) -> List[Dict]:
    valid_data = []
    for item in data:
        if "messages" not in item:
            continue
        messages = item["messages"]
        if not messages or len(messages) < 2:
            continue
        if messages[0]["role"] != "user":
            continue
        valid_data.append(item)
    return valid_data


def split_data(data: List[Dict], train_ratio: float = 0.9) -> tuple:
    train_data = []
    val_data = []
    for i, item in enumerate(data):
        if (i + 1) % 10 == 0:
            val_data.append(item)
        else:
            train_data.append(item)
    return train_data, val_data


def save_jsonl(data: List[Dict], file_path: Path):
    with open(file_path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def main():
    print("=" * 50)
    print("准备三月七训练数据")
    print("=" * 50)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("\n加载数据...")
    all_data = load_all_data()
    print(f"原始数据: {len(all_data)} 条")

    print("\n验证数据...")
    valid_data = validate_data(all_data)
    print(f"有效数据: {len(valid_data)} 条")

    print("\n划分数据集...")
    train_data, val_data = split_data(valid_data)
    print(f"训练集: {len(train_data)} 条")
    print(f"验证集: {len(val_data)} 条")

    train_path = OUTPUT_DIR / "train.jsonl"
    val_path = OUTPUT_DIR / "val.jsonl"

    save_jsonl(train_data, train_path)
    save_jsonl(val_data, val_path)

    print(f"\n数据已保存:")
    print(f"  训练集: {train_path}")
    print(f"  验证集: {val_path}")

    print("\n数据示例:")
    for i, item in enumerate(train_data[:3], 1):
        print(f"\n--- 示例 {i} ---")
        for msg in item["messages"][:4]:
            print(f"  {msg['role']}: {msg['content'][:50]}...")


if __name__ == "__main__":
    main()
