import asyncio
import json
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, List, AsyncGenerator

import ollama

import config
from inference import March7thChatbot
from tts_service import TTSService, wait_for_memory_release, check_gpu_memory, clear_gpu_memory
from persona_manager import PersonaManager, get_persona_manager
from character_config import CharacterConfigManager, CharacterConfig
from user_preference import get_preference_analyzer, extract_and_save_preferences


SENTENCE_END_PATTERN = re.compile(r'[。！？.!?\n]')
EMOTION_PATTERN = re.compile(r'\[EMOTION:\s*(\w+)\]', re.IGNORECASE)


def clean_emotion_tag(text: str) -> str:
    return EMOTION_PATTERN.sub('', text).strip()


def log(msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)


class VoiceChatController:
    def __init__(
        self,
        use_rag: bool = True,
        top_k: int = 3,
        distance_threshold: float = 1.0,
        use_persona: bool = True,
        model_name: str = None,
        character_id: str = None,
    ):
        self.character_manager = CharacterConfigManager()
        self.current_character: Optional[CharacterConfig] = None
        self.current_character_id: Optional[str] = None

        if character_id:
            self.current_character = self.character_manager.get_character(
                character_id)
            self.current_character_id = character_id
        else:
            all_characters = self.character_manager.get_all_characters()
            if all_characters:
                self.current_character = all_characters[0]
                self.current_character_id = self.current_character.id
                log(f"未指定角色，使用默认角色: {self.current_character.name}")

        llm_model = model_name
        llm_system_prompt = None
        if self.current_character:
            llm_model = model_name or self.current_character.llm_config.model
            llm_system_prompt = self.current_character.llm_config.system_prompt
            if self.current_character.rag_config.enabled is not None:
                use_rag = self.current_character.rag_config.enabled
            top_k = self.current_character.rag_config.top_k
            distance_threshold = self.current_character.rag_config.distance_threshold

        self.persona_manager = get_persona_manager() if use_persona else None

        llm_api_config = None
        if self.current_character and self.current_character.api_config and self.current_character.api_config.provider_type != "ollama":
            llm_api_config = self.current_character.api_config

        collection_name = ""
        if self.current_character:
            collection_name = self.current_character.rag_config.collection_name or ""

        self.llm = March7thChatbot(
            use_rag=use_rag,
            top_k=top_k,
            distance_threshold=distance_threshold,
            persona_manager=self.persona_manager,
            model_name=llm_model,
            system_prompt=llm_system_prompt,
            api_config=llm_api_config,
            collection_name=collection_name,
        )
        self.llm.character_config = self.current_character

        tts_gpt_path = None
        tts_sovits_path = None
        tts_ref_audio = None
        tts_ref_text = None
        tts_port = None
        if self.current_character:
            tts_gpt_path = self.current_character.tts_config.gpt_weight or None
            tts_sovits_path = self.current_character.tts_config.sovits_weight or None
            tts_ref_audio = self.current_character.tts_config.ref_audio_path or None
            tts_ref_text = self.current_character.tts_config.ref_audio_text or None
            tts_port = self.current_character.tts_config.port or None

        self.tts = TTSService(
            gpt_path=tts_gpt_path,
            sovits_path=tts_sovits_path,
            ref_audio_path=tts_ref_audio,
            ref_text=tts_ref_text,
            port=tts_port,
        )

        from emotion_classifier import LLMEmotionClassifier, get_emotion_api_config
        from llm_provider import get_provider

        emotion_llm_provider = None
        emotion_api_config = get_emotion_api_config(self.current_character)
        if emotion_api_config and emotion_api_config.provider_type != "ollama":
            try:
                emotion_llm_provider = get_provider(emotion_api_config)
            except Exception:
                emotion_llm_provider = None
        self.emotion_classifier = LLMEmotionClassifier(llm_provider=emotion_llm_provider)

        self.llm_active = False
        self.tts_active = False
        self._last_dialogue_id = None
        self._tts_lock = threading.Lock()
        self._init_llm()

    def switch_character(self, character_id: str) -> bool:
        character = self.character_manager.get_character(character_id)
        if not character:
            log(f"角色不存在: {character_id}")
            return False

        self.current_character = character
        self.current_character_id = character_id

        self.llm.model_name = character.llm_config.model
        self.llm.set_system_prompt(character.llm_config.system_prompt)
        self.llm.use_rag = character.rag_config.enabled
        self.llm.top_k = character.rag_config.top_k
        self.llm.distance_threshold = character.rag_config.distance_threshold
        self.llm.collection_name = character.rag_config.collection_name or ""
        self.llm.character_config = character

        self.tts.update_ref_audio(
            character.tts_config.ref_audio_path,
            character.tts_config.ref_audio_text,
        )
        self.tts.update_weights(
            character.tts_config.gpt_weight,
            character.tts_config.sovits_weight,
        )

        log(f"已切换到角色: {character.name} (ID: {character_id})")
        return True

    def is_api_mode(self):
        return self.llm.is_api_mode if hasattr(self.llm, 'is_api_mode') else False

    def get_current_character(self) -> Optional[CharacterConfig]:
        return self.current_character

    def get_current_character_id(self) -> Optional[str]:
        return self.current_character_id

    def _init_llm(self):
        log("初始化LLM...")
        self.llm.check_model()
        self.llm.load_rag()
        self.llm_active = True
        log(f"LLM初始化完成 | GPU显存: {check_gpu_memory():.0f}MB")

    def _ensure_llm_active(self) -> bool:
        if self.is_api_mode():
            self.llm_active = True
            return True
        if self.tts_active:
            self._release_tts()
        if not self.llm_active:
            log("激活LLM...")
            try:
                ollama.chat(model=config.LLM_MODEL, messages=[
                            {"role": "user", "content": "你好"}])
                self.llm_active = True
                log(f"LLM已激活 | GPU显存: {check_gpu_memory():.0f}MB")
            except Exception as e:
                log(f"LLM激活失败: {e}")
                raise RuntimeError(f"Failed to activate LLM: {e}")
        return True

    def _release_llm(self) -> bool:
        if self.is_api_mode():
            return True
        if not self.llm_active:
            return True

        log("释放LLM显存...")
        try:
            ollama.generate(model=config.LLM_MODEL, prompt="", keep_alive=0)
            log("已发送卸载命令 (keep_alive=0)")
        except Exception as e:
            log(f"卸载LLM失败: {e}")

        released = wait_for_memory_release()
        if not released:
            log("警告: LLM显存可能未完全释放")

        self.llm_active = False
        clear_gpu_memory()
        log(f"LLM已释放 | GPU显存: {check_gpu_memory():.0f}MB")
        return released

    def _ensure_tts_active(self) -> bool:
        if self.tts_active:
            return True

        with self._tts_lock:
            if self.tts_active:
                return True

            if self.llm_active and not self.is_api_mode():
                self._release_llm()

            log("启动TTS服务...")
            started = self.tts.start()
            if not started:
                log("TTS服务启动失败")
                raise RuntimeError("Failed to start TTS service")
            self.tts_active = True
            log(f"TTS服务已启动 | GPU显存: {check_gpu_memory():.0f}MB")

        return True

    def _release_tts(self) -> bool:
        if not self.tts_active:
            return True

        log("停止TTS服务...")
        self.tts.stop()

        released = wait_for_memory_release()
        if not released:
            log("警告: TTS显存可能未完全释放")

        self.tts_active = False
        clear_gpu_memory()
        log(f"TTS已停止 | GPU显存: {check_gpu_memory():.0f}MB")
        return released

    def _save_to_history(
        self,
        user_input: str,
        assistant_response: str,
        user_id: int = None,
        character: str = None,
        save_to_db: bool = True,
        rating: int = None,
        session_id: str = None,
        emotion: str = None,
    ) -> Optional[int]:
        conversation_id = None

        extracted_emotion = emotion
        emotion_match = EMOTION_PATTERN.search(assistant_response)
        if emotion_match:
            extracted_emotion = emotion_match.group(1).lower()
            log(f"从回复中提取情绪标签: {extracted_emotion}")

        clean_response = clean_emotion_tag(assistant_response)

        if save_to_db and user_id:
            from database import get_db, save_conversation
            db = get_db()
            char_name = character or (
                self.current_character.name if self.current_character else "default")
            conversation_id = save_conversation(
                db, user_id, char_name, user_input, clean_response, session_id, extracted_emotion
            )
            self._last_dialogue_id = conversation_id
            log(f"对话已保存到数据库 (ID: {conversation_id}, 用户: {user_id}, 会话: {session_id}, 情绪: {extracted_emotion})")

            if rating is not None:
                extract_and_save_preferences(user_id, user_input, rating)
                log(f"用户偏好已分析并保存 (评分: {rating})")

        if self.persona_manager:
            self._last_dialogue_id = self.persona_manager.save_dialogue(
                user_input=user_input,
                assistant_response=clean_response,
            )
        else:
            history_path = Path(config.HISTORY_FILE)
            record = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "messages": [
                    {"role": "user", "content": user_input},
                    {"role": "assistant", "content": clean_response},
                ],
            }

            with open(history_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return conversation_id

    def save_feedback(
        self,
        rating: int = None,
        dialogue_id: str = None,
        user_id: int = None,
    ) -> bool:
        if not self.persona_manager:
            return False

        target_id = dialogue_id or self._last_dialogue_id
        if not target_id:
            return False

        success = self.persona_manager.update_feedback(
            record_id=target_id,
            rating=rating,
        )

        if success and user_id and rating is not None:
            from database import get_db, get_conversations
            db = get_db()
            conversations = get_conversations(db, user_id, limit=1)
            if conversations:
                latest_conv = conversations[0]
                extract_and_save_preferences(
                    user_id,
                    latest_conv['user_input'],
                    rating
                )
                log(f"评分反馈已更新用户偏好 (评分: {rating})")

        return success

    def get_last_dialogue_id(self) -> Optional[str]:
        return self._last_dialogue_id

    def process_user_input(
        self,
        user_input: str,
        temperature: float = 1.0,
        top_p: float = 0.9,
        character_id: str = None,
        model_name: str = None,
        user_id: int = None,
        emotion: str = "neutral",
        session_id: str = None,
    ) -> Tuple[str, Optional[bytes], Optional[int], dict]:
        log(f"========== 开始处理用户输入 ==========")
        log(f"用户输入: {user_input[:50]}...")

        debug_info = {
            "user_input": user_input,
            "character_id": character_id or self.current_character_id,
            "model_name": model_name or self.llm.model_name,
            "temperature": temperature,
            "top_p": top_p,
            "emotion": emotion,
            "llm": {},
            "rag": {},
            "tts": {},
            "total_time": 0,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        total_start = time.time()

        if character_id and character_id != self.current_character_id:
            self.switch_character(character_id)

        t0 = time.time()
        self._ensure_llm_active()

        log("LLM生成回复中...")
        t1 = time.time()
        result = self.llm.generate(
            user_input,
            temperature=temperature,
            top_p=top_p,
            model_name=model_name,
        )
        response_text = result["response"]
        llm_debug = result["debug_info"]
        llm_time = time.time() - t1
        log(f"LLM生成完成，耗时: {llm_time:.2f}s")
        log(f"回复内容: {response_text[:100]}...")

        debug_info["llm"] = {
            "generation_time": round(llm_time, 3),
            "input_tokens": llm_debug["tokens"]["input_tokens"],
            "output_tokens": llm_debug["tokens"]["output_tokens"],
            "raw_output": llm_debug["raw_output"],
            "full_prompt": llm_debug["full_prompt"],
        }
        debug_info["rag"] = llm_debug["rag"]

        detected_emotion = emotion
        emotion_match = EMOTION_PATTERN.search(response_text)
        if emotion_match:
            detected_emotion = emotion_match.group(1).lower()
            log(f"检测到情绪标签: {detected_emotion}")
        if not detected_emotion or detected_emotion == "neutral":
            try:
                detected_emotion = self.emotion_classifier.predict(response_text)
                log(f"LLM情绪分类结果: {detected_emotion}")
            except Exception:
                detected_emotion = "neutral"

        clean_response = clean_emotion_tag(response_text)

        char_name = self.current_character.name if self.current_character else None
        conversation_id = self._save_to_history(
            user_input, response_text, user_id=user_id, character=char_name, 
            session_id=session_id, emotion=detected_emotion
        )

        self._release_llm()

        log("TTS合成语音中...")
        t2 = time.time()
        self._ensure_tts_active()

        tts_text = clean_response
        actual_character_id = character_id or self.current_character_id
        audio_bytes = self.tts.synthesize(
            clean_response,
            emotion=detected_emotion if detected_emotion else "neutral",
            character_id=actual_character_id,
        )
        tts_time = time.time() - t2
        log(f"TTS合成完成，耗时: {tts_time:.2f}s，音频大小: {len(audio_bytes) if audio_bytes else 0} bytes")

        debug_info["tts"] = {
            "text": tts_text,
            "synthesis_time": round(tts_time, 3),
            "audio_size_bytes": len(audio_bytes) if audio_bytes else 0,
            "emotion": detected_emotion,
        }

        self._release_tts()

        total_time = time.time() - total_start
        debug_info["total_time"] = round(total_time, 3)

        log(f"========== 处理完成，总耗时: {total_time:.2f}s ==========")
        return clean_response, audio_bytes, conversation_id, debug_info

    def chat_text_only(
        self,
        user_input: str,
        temperature: float = 1.0,
        top_p: float = 0.9,
    ) -> str:
        self._ensure_llm_active()

        result = self.llm.generate(
            user_input,
            temperature=temperature,
            top_p=top_p,
        )
        response_text = result["response"]

        self._save_to_history(user_input, response_text)

        return response_text

    def llm_chat(
        self,
        user_input: str,
        temperature: float = 1.0,
        top_p: float = 0.9,
        model_name: str = None,
        use_rag: bool = None,
        system_prompt: str = None,
    ) -> Tuple[str, dict]:
        log(f"========== LLM独立测试 ==========")
        log(f"用户输入: {user_input[:50]}...")

        t0 = time.time()
        self._ensure_llm_active()

        original_use_rag = self.llm.use_rag
        if use_rag is not None:
            self.llm.use_rag = use_rag

        log(f"LLM生成回复中... (模型: {model_name or self.llm.model_name})")
        t1 = time.time()
        result = self.llm.generate(
            user_input,
            temperature=temperature,
            top_p=top_p,
            model_name=model_name,
            system_prompt=system_prompt,
        )
        response_text = result["response"]
        llm_debug = result["debug_info"]
        log(f"LLM生成完成，耗时: {time.time()-t1:.2f}s")

        if use_rag is not None:
            self.llm.use_rag = original_use_rag

        debug_info = {
            "model": model_name or self.llm.model_name,
            "use_rag": use_rag if use_rag is not None else self.llm.use_rag,
            "history_turns": self.llm.get_history_length(),
            "response_time": round(time.time() - t0, 2),
            "response_length": len(response_text),
            "input_tokens": llm_debug["tokens"]["input_tokens"],
            "output_tokens": llm_debug["tokens"]["output_tokens"],
            "rag_documents": llm_debug["rag"]["documents"],
            "full_prompt": llm_debug["full_prompt"],
            "raw_output": llm_debug["raw_output"],
        }

        log(
            f"========== LLM测试完成，总耗时: {debug_info['response_time']}s ==========")
        return response_text, debug_info

    def synthesize_audio(
        self,
        text: str,
        ref_audio_path: str = None,
        ref_text: str = None,
        speed: float = 1.0,
        emotion: str = "neutral",
        character_id: str = None,
    ) -> bytes:
        if ref_audio_path:
            self.tts.ref_audio_path = ref_audio_path
        if ref_text:
            self.tts.ref_text = ref_text
        self._ensure_tts_active()
        audio_bytes = self.tts.synthesize(
            text, speed=speed, emotion=emotion, character_id=character_id)
        self._release_tts()
        return audio_bytes

    async def synthesize_audio_async(self, text: str, emotion: str = "neutral", character_id: str = None) -> bytes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._synthesize_for_stream, text, emotion, character_id)

    def _synthesize_for_stream(self, text: str, emotion: str = "neutral", character_id: str = None) -> bytes:
        if not self.tts_active:
            self._ensure_tts_active()
        emotion = emotion or "neutral"
        try:
            audio_bytes = self.tts.synthesize(
                text, emotion=emotion, character_id=character_id)
            return audio_bytes
        except Exception as e:
            log(f"TTS合成失败: {e}")
            return b''

    async def process_stream(
        self,
        user_input: str,
        temperature: float = 1.0,
        top_p: float = 0.9,
        character_id: str = None,
        model_name: str = None,
        user_id: int = None,
        emotion: str = "neutral",
        session_id: str = None,
    ) -> AsyncGenerator[dict, None]:
        log(f"========== 开始流式处理用户输入 ==========")
        log(f"用户输入: {user_input[:50]}...")

        if character_id and character_id != self.current_character_id:
            self.switch_character(character_id)

        self._ensure_llm_active()

        text_buffer = ""
        full_response = ""
        sentences_to_synthesize = []
        conversation_id = None
        actual_character_id = character_id or self.current_character_id

        def find_sentence_end(buffer: str) -> Tuple[str, str]:
            match = SENTENCE_END_PATTERN.search(buffer)
            if match:
                end_pos = match.end()
                sentence = buffer[:end_pos]
                remaining = buffer[end_pos:]
                return sentence, remaining
            return "", buffer

        try:
            for chunk in self.llm.generate_stream(
                user_input,
                temperature=temperature,
                top_p=top_p,
                model_name=model_name,
            ):
                if chunk.startswith("[ERROR]"):
                    yield {"type": "error", "error": chunk[7:].strip()}
                    return

                text_buffer += chunk
                full_response += chunk

                sentence, text_buffer = find_sentence_end(text_buffer)
                if sentence:
                    clean_sentence = clean_emotion_tag(sentence)
                    if clean_sentence:
                        yield {"type": "text", "content": clean_sentence}
                    sentences_to_synthesize.append(sentence)

            if text_buffer.strip():
                clean_buffer = clean_emotion_tag(text_buffer)
                if clean_buffer:
                    yield {"type": "text", "content": clean_buffer}
                sentences_to_synthesize.append(text_buffer)

            detected_emotion = emotion
            emotion_match = EMOTION_PATTERN.search(full_response)
            if emotion_match:
                detected_emotion = emotion_match.group(1).lower()
                log(f"检测到情绪标签: {detected_emotion}")
            if not detected_emotion or detected_emotion == "neutral":
                try:
                    detected_emotion = self.emotion_classifier.predict(full_response)
                    log(f"LLM情绪分类结果: {detected_emotion}")
                except Exception:
                    detected_emotion = "neutral"

            full_text_for_tts = ''.join(sentences_to_synthesize)
            clean_full_text = clean_emotion_tag(full_text_for_tts)
            
            if clean_full_text:
                try:
                    audio_bytes = await self.synthesize_audio_async(clean_full_text, detected_emotion, actual_character_id)
                    if audio_bytes:
                        import base64
                        audio_base64 = base64.b64encode(
                            audio_bytes).decode('utf-8')
                        yield {
                            "type": "audio",
                            "audio": audio_base64,
                            "text": clean_full_text
                        }
                except Exception as e:
                    log(f"TTS处理失败: {e}")

            char_name = self.current_character.name if self.current_character else None
            conversation_id = self._save_to_history(
                user_input, full_response, user_id=user_id, character=char_name, 
                session_id=session_id, emotion=detected_emotion
            )

            yield {"type": "done", "conversation_id": conversation_id}

            log(f"========== 流式处理完成 ==========")

        except Exception as e:
            log(f"流式处理错误: {e}")
            yield {"type": "error", "error": str(e)}
        finally:
            if self.tts_active:
                self._release_tts()
            self._release_llm()

    def clear_history(self):
        self.llm.clear_history()
        self._last_dialogue_id = None

        history_path = Path(config.HISTORY_FILE)
        if history_path.exists():
            history_path.unlink()

        if self.persona_manager:
            self.persona_manager.clear_all()

    def load_session_history(self, session_id: str, user_id: int = None) -> bool:
        from database import get_db, get_session, get_session_conversations

        db = get_db()
        session = get_session(db, session_id)
        if not session:
            log(f"会话不存在: {session_id}")
            return False

        if user_id is not None and session['user_id'] != user_id:
            log(f"无权访问会话: {session_id}")
            return False

        conversations = get_session_conversations(db, session_id)
        if not conversations:
            log(f"会话无历史记录: {session_id}")
            return True

        self.llm.clear_history()

        messages = []
        for conv in conversations:
            messages.append({"role": "user", "content": conv['user_input']})
            messages.append({"role": "assistant", "content": conv['bot_reply']})

        self.llm.conversation_history = messages

        log(f"已加载会话历史: {session_id}, 共 {len(messages)} 条消息")
        return True

    def switch_session(self, session_id: str, user_id: int = None) -> bool:
        from database import get_db, get_session

        db = get_db()
        session = get_session(db, session_id)
        if not session:
            log(f"会话不存在: {session_id}")
            return False

        if user_id is not None and session['user_id'] != user_id:
            log(f"无权切换到会话: {session_id}")
            return False

        self.llm.clear_history()
        self._last_dialogue_id = None
        log(f"已清空当前对话历史")

        character_id = session.get('character_id')
        if character_id and character_id != self.current_character_id:
            self.switch_character(character_id)
            log(f"已切换到角色: {character_id}")

        success = self.load_session_history(session_id, user_id)
        if success:
            log(f"会话切换成功: {session_id}")
        else:
            log(f"会话切换失败: {session_id}")

        return success

    def get_status(self) -> dict:
        gpu_memory = check_gpu_memory()
        return {
            "llm_active": self.llm_active,
            "tts_active": self.tts_active,
            "gpu_memory_mb": gpu_memory,
            "history_turns": self.llm.get_history_length(),
            "current_character_id": self.current_character_id,
            "current_character_name": self.current_character.name if self.current_character else None,
        }

    def shutdown(self):
        if self.tts_active:
            self._release_tts()
        if self.llm_active:
            self._release_llm()


_controller_instance: Optional[VoiceChatController] = None


def get_controller(character_id: str = None) -> VoiceChatController:
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = VoiceChatController(character_id=character_id)
    elif character_id and character_id != _controller_instance.current_character_id:
        _controller_instance.switch_character(character_id)
    return _controller_instance


def handle_chat(user_input: str, character_id: str = None, user_id: int = None) -> Tuple[str, Optional[bytes], str, Optional[int], dict]:
    if not user_input or not user_input.strip():
        return "", None, "请输入内容", None, {}

    controller = get_controller(character_id=character_id)

    try:
        response_text, audio_bytes, conversation_id, debug_info = controller.process_user_input(
            user_input.strip(),
            character_id=character_id,
            user_id=user_id,
        )
        status = f"完成 | GPU显存: {check_gpu_memory():.0f}MB"
        return response_text, audio_bytes, status, conversation_id, debug_info
    except Exception as e:
        return "", None, f"错误: {str(e)}", None, {}


def clear_history() -> str:
    controller = get_controller()
    controller.clear_history()
    return "对话历史已清除"


def save_feedback(rating: int = None) -> str:
    controller = get_controller()
    success = controller.save_feedback(rating=rating)
    if success:
        return "反馈已保存"
    return "保存反馈失败"


def get_system_status() -> str:
    controller = get_controller()
    status = controller.get_status()
    char_info = ""
    if status.get("current_character_name"):
        char_info = f" | 角色: {status['current_character_name']}"
    return f"LLM: {'运行中' if status['llm_active'] else '已停止'} | TTS: {'运行中' if status['tts_active'] else '已停止'} | GPU: {status['gpu_memory_mb']:.0f}MB{char_info}"
