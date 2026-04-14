"""
角色模板管理模块
提供角色模板的加载、导入功能
"""
import json
import os
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "resources" / "character_templates"


def get_templates_dir() -> Path:
    templates_dir = Path(os.environ.get("CHARACTER_TEMPLATES_DIR", str(TEMPLATES_DIR)))
    templates_dir.mkdir(parents=True, exist_ok=True)
    return templates_dir


def load_template_file(template_path: Path) -> Optional[Dict[str, Any]]:
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Templates] 加载模板文件失败 {template_path}: {e}")
        return None


def load_templates() -> List[Dict[str, Any]]:
    templates_dir = get_templates_dir()
    templates = []

    if not templates_dir.exists():
        return templates

    for template_file in templates_dir.glob("*_template.json"):
        template_data = load_template_file(template_file)
        if template_data:
            templates.append(template_data)

    return templates


def get_template(template_id: str) -> Optional[Dict[str, Any]]:
    templates = load_templates()
    for template in templates:
        if template.get("id") == template_id:
            return template
    return None


def get_all_templates() -> List[Dict[str, Any]]:
    return load_templates()


def get_template_summary(template: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": template.get("id", ""),
        "name": template.get("name", ""),
        "avatar_path": template.get("avatar_path", ""),
        "llm_model": template.get("llm_config", {}).get("model", "deepseek-r1:8b"),
        "system_prompt_preview": template.get("llm_config", {}).get("system_prompt", "")[:100] + "..." if len(template.get("llm_config", {}).get("system_prompt", "")) > 100 else template.get("llm_config", {}).get("system_prompt", ""),
        "rag_enabled": template.get("rag_config", {}).get("enabled", True),
        "rag_collection": template.get("rag_config", {}).get("collection_name", ""),
    }


def import_template_to_user(template_id: str, user_id: int) -> Optional[Dict[str, Any]]:
    from character_config import CharacterConfig, LLMConfig, TTSConfig, RAGConfig, PersonaConfig, MemoryConfig, CharacterConfigManager

    template = get_template(template_id)
    if not template:
        print(f"[Templates] 模板不存在: {template_id}")
        return None

    manager = CharacterConfigManager()

    new_id = f"{template_id}_{user_id}"

    if manager.character_exists(new_id):
        print(f"[Templates] 用户 {user_id} 已拥有角色 {new_id}")
        return None

    llm_data = template.get("llm_config", {})
    tts_data = template.get("tts_config", {})
    rag_data = template.get("rag_config", {})
    persona_data = template.get("persona_config", {})
    memory_data = template.get("memory_config", {})

    llm_config = LLMConfig(
        model=llm_data.get("model", "deepseek-r1:8b"),
        system_prompt=llm_data.get("system_prompt", ""),
        temperature=llm_data.get("temperature", 1.0),
        top_p=llm_data.get("top_p", 0.9),
        max_tokens=llm_data.get("max_tokens", 1024),
    )

    tts_config = TTSConfig(
        gpt_weight=tts_data.get("gpt_weight", ""),
        sovits_weight=tts_data.get("sovits_weight", ""),
        ref_audio_path=tts_data.get("ref_audio_path", ""),
        ref_audio_text=tts_data.get("ref_audio_text", ""),
        port=tts_data.get("port", 9880),
        version=tts_data.get("version", "v2ProPlus"),
    )

    rag_config = RAGConfig(
        collection_name=rag_data.get("collection_name", ""),
        enabled=rag_data.get("enabled", True),
        top_k=rag_data.get("top_k", 3),
        distance_threshold=rag_data.get("distance_threshold", 1.0),
    )

    persona_config = PersonaConfig(
        file=persona_data.get("file", "user_persona.jsonl"),
        db_dir=persona_data.get("db_dir", "persona_db"),
        min_rating=persona_data.get("min_rating", 4),
        top_k=persona_data.get("top_k", 2),
    )

    memory_config = MemoryConfig(
        history_limit=memory_data.get("history_limit", 50),
        max_context_tokens=memory_data.get("max_context_tokens", 16384),
        output_reserved=memory_data.get("output_reserved", 500),
        min_output_tokens=memory_data.get("min_output_tokens", 100),
    )

    character = CharacterConfig(
        id=new_id,
        name=template.get("name", ""),
        avatar_path=template.get("avatar_path", ""),
        llm_config=llm_config,
        tts_config=tts_config,
        rag_config=rag_config,
        persona_config=persona_config,
        memory_config=memory_config,
    )

    success = manager.add_character(character)
    if not success:
        print(f"[Templates] 导入角色失败: {new_id}")
        return None

    return character.to_dict()


def get_templates_summary() -> List[Dict[str, Any]]:
    templates = load_templates()
    return [get_template_summary(t) for t in templates]


def main():
    print("=" * 50)
    print("角色模板管理模块测试")
    print("=" * 50)

    templates_dir = get_templates_dir()
    print(f"\n模板目录: {templates_dir}")
    print(f"目录存在: {templates_dir.exists()}")

    templates = load_templates()
    print(f"\n已加载模板数量: {len(templates)}")

    for template in templates:
        summary = get_template_summary(template)
        print(f"\n模板 ID: {summary['id']}")
        print(f"  名称: {summary['name']}")
        print(f"  LLM: {summary['llm_model']}")
        print(f"  RAG: {summary['rag_enabled']}")


if __name__ == "__main__":
    main()