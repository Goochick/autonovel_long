# ============================================================
# AutoNovel-CN API 客户端
# 统一的 API 调用层，支持 OpenAI 兼容格式
# ============================================================

import os
import sys
import json
import time
import logging
from typing import Optional, Dict, Any, List, Union
from pathlib import Path

import httpx

# 将项目根目录添加到 sys.path，以便正确导入 config
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# 使用 importlib 直接导入 config 模块（避免包名冲突）
import importlib.util
_config_spec = importlib.util.spec_from_file_location("config", _project_root / "config.py")
config = importlib.util.module_from_spec(_config_spec)
_config_spec.loader.exec_module(config)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("api_client")

# ============================================================
# 异常类
# ============================================================

class APIError(Exception):
    """API 调用基础异常"""
    def __init__(self, message: str, provider: str = "", status_code: int = 0):
        self.message = message
        self.provider = provider
        self.status_code = status_code
        super().__init__(self.message)

class APIRateLimitError(APIError):
    """API 限流错误"""
    pass

class APITimeoutError(APIError):
    """API 超时错误"""
    pass

class ModelUnavailableError(APIError):
    """模型不可用错误"""
    pass

# ============================================================
# API 客户端类
# ============================================================

class TokenBudgetExceeded(Exception):
    """Token 预算超支异常"""
    pass


class APIClient:
    """
    统一的 API 客户端，支持 OpenAI 兼容格式的多个中文 API
    
    支持的 API：
    - DeepSeek V3（主力生成）
    - DeepSeek R1（关键审核/推理）
    - Qwen Turbo（快速草稿）
    - GLM-4-Flash（免费，机械检测）
    
    内置 Token 计数器与预算控制：
    - 每次调用自动记录消耗的 tokens
    - 超过预算时抛出 TokenBudgetExceeded 异常
    - 可随时查询当前消耗和预估费用
    """
    
    def __init__(self, default_writer_api: str = None, default_judge_api: str = None):
        """
        初始化 API 客户端
        
        Args:
            default_writer_api: 默认写作 API，None 则使用配置文件的值
            default_judge_api: 默认审核 API，None 则使用配置文件的值
        """
        self.writers_api = default_writer_api or config.DEFAULT_WRITER_API
        self.judge_api = default_judge_api or config.DEFAULT_JUDGE_API
        self.route_map = config.ROUTE_MAP.copy()
        self.providers = config.API_PROVIDERS.copy()
        
        # Token 计数器
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._call_count = 0
        self._per_provider_tokens = {}  # {provider: {"input": n, "output": n}}
        self._per_phase_tokens = {}     # {phase: {"input": n, "output": n}}
        self._current_phase = "default"
        
        # 预算上限（从 config 读取，千tokens → tokens）
        self._budget_total = config.TOKEN_BUDGET_K * 1000 if config.TOKEN_BUDGET_K > 0 else None
        self._per_phase_limit = config.PER_PHASE_LIMIT_K * 1000 if config.PER_PHASE_LIMIT_K > 0 else None
        self._per_chapter_revision_limit = config.PER_CHAPTER_REVISION_LIMIT_K * 1000 if config.PER_CHAPTER_REVISION_LIMIT_K > 0 else None
        self._show_cost = config.SHOW_COST_ESTIMATE
        
        # 验证 API key
        self._validate_api_keys()
    
    def set_phase(self, phase_name: str):
        """设置当前阶段名称（用于分阶段统计）"""
        self._current_phase = phase_name
    
    def is_configured(self) -> bool:
        """检查是否有可用的 API Key"""
        for key_name in ["DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY", "ZHIPU_API_KEY"]:
            if os.environ.get(key_name):
                return True
        return False
    
    def get_usage(self) -> dict:
        """获取当前 token 使用统计"""
        total = self._total_input_tokens + self._total_output_tokens
        cost = self._estimate_cost(self._total_input_tokens, self._total_output_tokens)
        
        return {
            "total_tokens": total,
            "input_tokens": self._total_input_tokens,
            "output_tokens": self._total_output_tokens,
            "call_count": self._call_count,
            "estimated_cost_yuan": round(cost, 4),
            "budget_remaining": (self._budget_total - total) if self._budget_total else None,
            "per_provider": dict(self._per_provider_tokens),
            "per_phase": dict(self._per_phase_tokens),
        }
    
    def print_usage(self):
        """打印当前使用统计"""
        usage = self.get_usage()
        print(f"\n{'='*50}")
        print(f"📊 Token 使用统计")
        print(f"{'='*50}")
        print(f"总调用次数: {usage['call_count']}")
        print(f"总 Tokens: {usage['total_tokens']:,} (输入 {usage['input_tokens']:,} + 输出 {usage['output_tokens']:,})")
        print(f"预估费用: ¥{usage['estimated_cost_yuan']}")
        if usage['budget_remaining'] is not None:
            pct = (1 - usage['budget_remaining'] / self._budget_total) * 100
            print(f"预算剩余: {usage['budget_remaining']:,} tokens ({pct:.1f}% 已用)")
        print(f"{'='*50}")
    
    def check_budget(self, estimated_input: int = 0, estimated_output: int = 0):
        """
        检查是否超出预算
        
        Args:
            estimated_input: 预估的输入 tokens
            estimated_output: 预估的输出 tokens
            
        Raises:
            TokenBudgetExceeded: 超出预算时抛出
        """
        total = self._total_input_tokens + self._total_output_tokens
        estimated_total = estimated_input + estimated_output
        
        # 全局预算检查
        if self._budget_total and (total + estimated_total) > self._budget_total:
            raise TokenBudgetExceeded(
                f"全局 token 预算已耗尽！已用 {total:,}，预算 {self._budget_total:,}，"
                f"本次预估 {estimated_total:,}"
            )
        
        # 阶段预算检查
        if self._per_phase_limit:
            phase_usage = self._per_phase_tokens.get(self._current_phase, {"input": 0, "output": 0})
            phase_total = phase_usage["input"] + phase_usage["output"]
            if (phase_total + estimated_total) > self._per_phase_limit:
                raise TokenBudgetExceeded(
                    f"阶段 [{self._current_phase}] token 预算已耗尽！"
                    f"已用 {phase_total:,}，限额 {self._per_phase_limit:,}"
                )
    
    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """估算费用（元）"""
        # 按各 provider 使用比例估算，简化为按主力 provider 计算
        if not self._per_provider_tokens:
            # 没有记录时用 DeepSeek V4 Flash 费率估算
            pricing = config.PRICING.get("deepseek_flash", {"input": 0.001, "output": 0.002})
            return (input_tokens / 1000 * pricing["input"]) + (output_tokens / 1000 * pricing["output"])
        
        total_cost = 0.0
        for provider, tokens in self._per_provider_tokens.items():
            pricing = config.PRICING.get(provider, {"input": 0.002, "output": 0.008})
            # 按 provider 的 input/output 比例分配
            provider_total = tokens["input"] + tokens["output"]
            if provider_total > 0:
                p_input = tokens["input"]
                p_output = tokens["output"]
                total_cost += (p_input / 1000 * pricing["input"]) + (p_output / 1000 * pricing["output"])
        
        return total_cost
    
    def _record_usage(self, provider_name: str, input_tokens: int, output_tokens: int):
        """记录 token 使用量"""
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        self._call_count += 1
        
        # 按 provider 统计
        if provider_name not in self._per_provider_tokens:
            self._per_provider_tokens[provider_name] = {"input": 0, "output": 0}
        self._per_provider_tokens[provider_name]["input"] += input_tokens
        self._per_provider_tokens[provider_name]["output"] += output_tokens
        
        # 按阶段统计
        phase = self._current_phase
        if phase not in self._per_phase_tokens:
            self._per_phase_tokens[phase] = {"input": 0, "output": 0}
        self._per_phase_tokens[phase]["input"] += input_tokens
        self._per_phase_tokens[phase]["output"] += output_tokens
        
        # 显示单次调用费用
        if self._show_cost:
            pricing = config.PRICING.get(provider_name, {"input": 0, "output": 0})
            call_cost = (input_tokens / 1000 * pricing["input"]) + (output_tokens / 1000 * pricing["output"])
            print(f"  💰 [{provider_name}] 本次 {input_tokens + output_tokens:,} tokens, ¥{call_cost:.4f}", end="")
            if self._budget_total:
                remaining = self._budget_total - self._total_input_tokens - self._total_output_tokens
                print(f" | 剩余预算 {remaining:,} tokens")
            else:
                total_cost = self._estimate_cost(self._total_input_tokens, self._total_output_tokens)
                print(f" | 累计 ¥{total_cost:.4f}")
    
    def _validate_api_keys(self):
        """验证必要的 API key 是否配置"""
        required_keys = ["DEEPSEEK_API_KEY"]
        missing = []
        for key in required_keys:
            if not os.environ.get(key):
                missing.append(key)
        
        if missing:
            logger.warning(
                f"缺少以下 API Key: {', '.join(missing)}。"
                f"请在 .env 文件中配置或在环境变量中设置。"
            )
    
    def _get_provider(self, provider_name: str) -> Dict[str, Any]:
        """获取提供商配置"""
        if provider_name not in self.providers:
            raise ValueError(f"未知的 API 提供商: {provider_name}")
        
        provider = self.providers[provider_name].copy()
        
        # 从环境变量获取最新的 API key
        api_key_env = provider.get("api_key_env")
        if api_key_env:
            provider["api_key"] = os.environ.get(api_key_env, "")
        
        return provider
    
    def _make_request(
        self,
        provider_name: str,
        messages: List[Dict[str, str]],
        model: str = None,
        max_tokens: int = 4000,
        temperature: float = 1.0,
        system: str = None,
        **extra_kwargs
    ) -> str:
        """
        发起 API 请求（核心方法）
        
        Args:
            provider_name: 提供商名称
            messages: 消息列表
            model: 模型名称，None 则使用提供商的默认模型
            max_tokens: 最大 token 数
            temperature: 温度参数
            system: 系统提示，None 则不设置
            **extra_kwargs: 其他参数
        
        Returns:
            API 响应的文本内容
        """
        provider = self._get_provider(provider_name)
        
        # 预算检查：预估本次调用消耗
        # 粗略估算：输入 tokens ≈ messages 文本长度/1.5，输出 tokens ≈ max_tokens
        estimated_input = sum(len(m.get("content", "")) // 1 for m in messages) if messages else 0
        if system:
            estimated_input += len(system) // 1
        estimated_output = max_tokens
        self.check_budget(estimated_input, estimated_output)
        
        # 构建消息列表
        request_messages = []
        if system:
            request_messages.append({"role": "system", "content": system})
        request_messages.extend(messages)
        
        # 构建 payload
        payload = {
            "model": model or provider["model"],
            "messages": request_messages,
            "max_tokens": min(max_tokens, provider["max_tokens_limit"]),
            "temperature": temperature,
        }
        
        # 添加额外参数
        payload.update(extra_kwargs)
        
        # 构建请求头
        headers = {
            "Authorization": f"Bearer {provider['api_key']}",
            "Content-Type": "application/json",
        }
        
        # 发起请求
        url = f"{provider['base_url']}/chat/completions"
        
        return self._execute_request(url, headers, payload, provider_name)
    
    def _execute_request(
        self,
        url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        provider_name: str,
        retry_count: int = 0
    ) -> str:
        """
        执行 HTTP 请求，包含重试逻辑
        
        Args:
            url: 请求 URL
            headers: 请求头
            payload: 请求体
            provider_name: 提供商名称（用于日志）
            retry_count: 当前重试次数
        
        Returns:
            API 响应的文本内容
        """
        max_retries = config.MAX_RETRIES
        
        try:
            with httpx.Client(timeout=config.REQUEST_TIMEOUT) as client:
                response = client.post(url, headers=headers, json=payload)
            
            # 处理响应状态码
            if response.status_code == 200:
                return self._parse_response(response, provider_name)
            
            elif response.status_code == 429:
                # 限流错误，指数退避重试
                if retry_count < max_retries:
                    wait_time = config.RETRY_BACKOFF ** (retry_count + 1)
                    logger.warning(
                        f"{provider_name} 限流，{wait_time:.1f}秒后重试..."
                    )
                    time.sleep(wait_time)
                    return self._execute_request(
                        url, headers, payload, provider_name, retry_count + 1
                    )
                else:
                    raise APIRateLimitError(
                        f"{provider_name} 达到最大重试次数",
                        provider_name,
                        response.status_code
                    )
            
            elif response.status_code == 400 or response.status_code == 404:
                # 模型不可用或其他错误
                error_detail = ""
                try:
                    error_detail = response.json().get("error", {}).get("message", "")
                except:
                    error_detail = response.text[:200]
                
                # 尝试降级
                provider = self._get_provider(provider_name)
                fallback = provider.get("fallback")
                if fallback and retry_count == 0:
                    logger.warning(
                        f"{provider_name} 返回错误: {error_detail}，"
                        f"尝试降级到 {fallback}..."
                    )
                    return self._fallback_request(fallback, payload)
                
                raise ModelUnavailableError(
                    f"{provider_name} 错误: {error_detail}",
                    provider_name,
                    response.status_code
                )
            
            elif response.status_code >= 500:
                # 服务器错误，重试
                if retry_count < max_retries:
                    wait_time = config.RETRY_BACKOFF ** (retry_count + 1)
                    logger.warning(
                        f"{provider_name} 服务器错误，{wait_time:.1f}秒后重试..."
                    )
                    time.sleep(wait_time)
                    return self._execute_request(
                        url, headers, payload, provider_name, retry_count + 1
                    )
                else:
                    raise APIError(
                        f"{provider_name} 服务器错误: {response.status_code}",
                        provider_name,
                        response.status_code
                    )
            
            else:
                raise APIError(
                    f"{provider_name} 返回错误: {response.status_code}",
                    provider_name,
                    response.status_code
                )
        
        except httpx.TimeoutException:
            # 网络超时，尝试重试一次
            if retry_count == 0:
                logger.warning(f"{provider_name} 超时，重试...")
                return self._execute_request(
                    url, headers, payload, provider_name, 1
                )
            raise APITimeoutError(
                f"{provider_name} 请求超时",
                provider_name
            )
    
    def _fallback_request(self, fallback_provider: str, payload: Dict[str, Any]) -> str:
        """降级到备选 API"""
        provider = self._get_provider(fallback_provider)
        
        # 修改 payload 中的模型
        payload["model"] = provider["model"]
        
        headers = {
            "Authorization": f"Bearer {provider['api_key']}",
            "Content-Type": "application/json",
        }
        
        url = f"{provider['base_url']}/chat/completions"
        return self._execute_request(url, headers, payload, fallback_provider)
    
    def _parse_response(self, response: httpx.Response, provider_name: str) -> str:
        """
        解析 API 响应
        
        处理不同 API 的响应格式差异，特别是 DeepSeek R1 的 reasoning_content
        同时记录 token 使用量
        """
        result = response.json()
        
        # 记录 token 用量（从 usage 字段提取）
        usage_info = result.get("usage", {})
        input_tokens = usage_info.get("prompt_tokens", 0)
        output_tokens = usage_info.get("completion_tokens", 0)
        
        # 如果 API 没返回 usage，用估算值（中文约 1.5 字/token）
        if input_tokens == 0 and output_tokens == 0:
            # 从 messages 估算 input
            input_tokens = 0  # 无法精确估算，记为 0
            output_tokens = 0
        
        self._record_usage(provider_name, input_tokens, output_tokens)
        
        # 获取响应内容
        # 标准 OpenAI 格式
        if "choices" in result and len(result["choices"]) > 0:
            message = result["choices"][0].get("message", {})
            content = message.get("content", "")
            
            # DeepSeek R1 特殊处理：可能包含 reasoning_content
            if provider_name == "deepseek_r1":
                reasoning = message.get("reasoning_content")
                if reasoning:
                    logger.debug(f"R1 思考过程（前100字）: {reasoning[:100]}...")
                    if not content:
                        content = reasoning
            
            return content
        
        # 错误响应
        if "error" in result:
            error_msg = result["error"].get("message", str(result["error"]))
            raise APIError(f"API 错误: {error_msg}", provider_name)
        
        raise APIError(f"未知的响应格式: {result}", provider_name)
    
    def chat(
        self,
        messages: Union[str, List[Dict[str, str]]],
        model: str = None,
        max_tokens: int = 4000,
        temperature: float = 1.0,
        system: str = None,
        provider: str = None
    ) -> str:
        """
        统一的聊天接口
        
        Args:
            messages: 消息内容（str）或消息列表（List[Dict]）
            model: 模型名称，None 则使用默认模型
            max_tokens: 最大 token 数
            temperature: 温度参数
            system: 系统提示
            provider: 强制使用特定 API
        
        Returns:
            API 响应的文本内容
        """
        # 处理 messages 参数
        if isinstance(messages, str):
            msg_list = [{"role": "user", "content": messages}]
        else:
            msg_list = messages
        
        # 选择 API
        if not provider:
            provider = self.writers_api
        
        return self._make_request(
            provider, msg_list, model, max_tokens, temperature, system
        )
    
    def chat_with_model(
        self,
        task_type: str,
        messages: Union[str, List[Dict[str, str]]],
        max_tokens: int = 4000,
        temperature: float = None,
        system: str = None
    ) -> str:
        """
        根据任务类型自动路由到最合适的 API
        
        Args:
            task_type: 任务类型，见 ROUTE_MAP
            messages: 消息内容
            max_tokens: 最大 token 数
            temperature: 温度参数，None 则使用 API 默认值
            system: 系统提示
        
        Returns:
            API 响应的文本内容
        """
        # 根据任务类型路由
        provider = self.route_map.get(task_type, self.writers_api)
        
        # 获取 provider 配置以获取默认温度
        provider_config = self._get_provider(provider)
        if temperature is None:
            temperature = provider_config.get("default_temperature", 1.0)
        
        logger.info(f"任务 [{task_type}] 路由到 [{provider_config['name']}]")
        
        return self.chat(
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            provider=provider
        )
    
    # ============================================================
    # 与原版兼容的接口
    # ============================================================
    
    def call_writer(self, prompt: str, max_tokens: int = 4000) -> str:
        """
        调用写作模型（兼容原版 call_writer 接口）
        
        Args:
            prompt: 用户 prompt
            max_tokens: 最大 token 数
        
        Returns:
            生成的文本
        """
        return self.chat_with_model(
            "chapter_draft",
            [{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=config.WRITER_TEMPERATURE,
            system=config.SYSTEM_PROMPT_WRITER if hasattr(config, 'SYSTEM_PROMPT_WRITER') else None
        )
    
    def call_judge(self, prompt: str, max_tokens: int = 2000) -> str:
        """
        调用审核模型（兼容原版 call_judge 接口）
        
        Args:
            prompt: 用户 prompt
            max_tokens: 最大 token 数
        
        Returns:
            审核结果
        """
        return self.chat_with_model(
            "chapter_eval",
            [{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=config.JUDGE_TEMPERATURE,
            system=config.SYSTEM_PROMPT_JUDGE if hasattr(config, 'SYSTEM_PROMPT_JUDGE') else None
        )
    
    def call_model(
        self,
        task_type: str,
        prompt: str,
        max_tokens: int = 4000,
        temperature: float = None,
        system_prompt: str = None
    ) -> str:
        """
        通用调用接口
        
        Args:
            task_type: 任务类型
            prompt: 用户 prompt
            max_tokens: 最大 token 数
            temperature: 温度参数
            system_prompt: 系统提示词（可选）
        
        Returns:
            生成的文本
        """
        return self.chat_with_model(
            task_type,
            [{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt
        )

    def call(
        self,
        prompt: str,
        system_prompt: str = None,
        api_name: str = None,
        max_tokens: int = 4000,
        temperature: float = 1.0
    ) -> str:
        """
        兼容原版脚本的统一调用接口
        所有 scripts/ 下的脚本通过此方法调用 API
        
        Args:
            prompt: 用户 prompt
            system_prompt: 系统提示词
            api_name: API 提供商名称（如 "deepseek_v3"），None 则用默认 writer API
            max_tokens: 最大 token 数
            temperature: 温度参数
        
        Returns:
            API 响应的文本内容
        """
        return self.chat(
            messages=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            provider=api_name
        )


# ============================================================
# 全局单例客户端
# ============================================================

_global_client: Optional[APIClient] = None

def get_global_client() -> APIClient:
    """获取全局 API 客户端（单例）"""
    global _global_client
    if _global_client is None:
        _global_client = APIClient()
    return _global_client

# 兼容原版的全局函数
def call_writer(prompt: str, max_tokens: int = 4000) -> str:
    """全局 call_writer 函数（兼容原版）"""
    return get_global_client().call_writer(prompt, max_tokens)

def call_judge(prompt: str, max_tokens: int = 2000) -> str:
    """全局 call_judge 函数（兼容原版）"""
    return get_global_client().call_judge(prompt, max_tokens)

def call_model(task_type: str, prompt: str, max_tokens: int = 4000) -> str:
    """全局 call_model 函数"""
    return get_global_client().call_model(task_type, prompt, max_tokens)

# 导出全局客户端实例
global_client = get_global_client()
