// MSAI 学习用 demo 的共享辅助工具。
// 所有 demo 都只从环境变量读取 API key —— 永远不要硬编码密钥。
using System;
using System.ClientModel;
using OpenAI;
using OpenAI.Chat;
using Microsoft.Extensions.AI;
using UnityEditor;
using UnityEngine;

namespace CBIM.Demos.Msai
{
    internal static class ApiKeyReader
    {
        public const string OpenAIEnvVar = "OPENAI_API_KEY";
        public const string AnthropicEnvVar = "ANTHROPIC_API_KEY";

        // 自定义 OpenAI 兼容 endpoint（团队代理用）。
        // 例：https://llm-proxy.tapsvc.com/v1
        // 留空 = 使用 OpenAI 官方 endpoint。
        public const string OpenAIBaseUrlEnvVar = "OPENAI_BASE_URL";
        public const string AnthropicBaseUrlEnvVar = "ANTHROPIC_BASE_URL";

        // 默认模型。代理上常见的 OpenAI 协议模型：gpt-5.4-mini / gpt-5.4 / claude-haiku-4-5 等。
        // 真实 OpenAI 官方账号则用 gpt-4o-mini。
        public const string DefaultModel = "gpt-5.4-mini";

        public static string GetOpenAIKey() => Environment.GetEnvironmentVariable(OpenAIEnvVar);
        public static string GetAnthropicKey() => Environment.GetEnvironmentVariable(AnthropicEnvVar);
        public static string GetOpenAIBaseUrl() => Environment.GetEnvironmentVariable(OpenAIBaseUrlEnvVar);
        public static string GetAnthropicBaseUrl() => Environment.GetEnvironmentVariable(AnthropicBaseUrlEnvVar);

        /// <summary>
        /// 当环境变量已设置时，返回 true 并填充 <paramref name="key"/>；否则返回 false，
        /// 并把对用户友好的提示写入 <paramref name="error"/>。
        /// </summary>
        public static bool RequireKey(string envVarName, out string key, out string error)
        {
            key = Environment.GetEnvironmentVariable(envVarName);
            if (string.IsNullOrWhiteSpace(key))
            {
                error = $"环境变量 {envVarName} 未设置。" +
                        "请用 setx 设为用户级或系统级持久环境变量（不只是当前 shell 临时变量），" +
                        "然后**完全退出 UnityHub 和 Unity** 再重启（Unity 是 UnityHub 子进程，" +
                        "继承的是 UnityHub 启动时的环境，只重启 Unity 进程不够）。";
                return false;
            }
            error = null;
            return true;
        }

        /// <summary>
        /// 绘制一个红色警告框和一个 "复制环境变量名" 按钮。
        /// 当 key 缺失时返回 true（调用方应直接跳过后续 GUI）。
        /// </summary>
        public static bool DrawMissingKeyWarning(string envVarName, string error)
        {
            var prev = GUI.color;
            GUI.color = new Color(1f, 0.4f, 0.4f);
            EditorGUILayout.HelpBox(error, MessageType.Error);
            GUI.color = prev;
            if (GUILayout.Button($"复制 '{envVarName}' 到剪贴板"))
            {
                EditorGUIUtility.systemCopyBuffer = envVarName;
            }
            return true;
        }
    }

    /// <summary>
    /// 共享的 OpenAI client 工厂。每个 demo 按需自行构建 ChatClient / IChatClient，
    /// 不在 demo 之间携带任何状态。
    ///
    /// 当 OPENAI_BASE_URL 环境变量已设置时，自动指向自定义 endpoint（团队代理）；
    /// 否则使用 OpenAI 官方 endpoint。
    /// </summary>
    internal static class DemoUtils
    {
        public static OpenAIClient NewOpenAIClient(string apiKey)
        {
            var baseUrl = ApiKeyReader.GetOpenAIBaseUrl();
            var credential = new ApiKeyCredential(apiKey);

            if (!string.IsNullOrWhiteSpace(baseUrl))
            {
                var options = new OpenAIClientOptions
                {
                    Endpoint = new Uri(baseUrl)
                };
                return new OpenAIClient(credential, options);
            }
            return new OpenAIClient(credential);
        }

        public static ChatClient NewChatClient(string apiKey, string model = ApiKeyReader.DefaultModel)
            => NewOpenAIClient(apiKey).GetChatClient(model);

        public static IChatClient NewIChatClient(string apiKey, string model = ApiKeyReader.DefaultModel)
            => NewChatClient(apiKey, model).AsIChatClient();
    }
}
