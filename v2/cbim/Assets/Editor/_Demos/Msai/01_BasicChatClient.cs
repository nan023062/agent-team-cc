// Demo 1：最基础的 IChatClient 调用。
// 验证 Microsoft.Extensions.AI 最底层能否打通真实的 OpenAI 接口。
using System;
using System.Collections.Generic;
using Microsoft.Extensions.AI;
using UnityEditor;
using UnityEngine;

namespace CBIM.Demos.Msai
{
    internal sealed class Demo01_BasicChatClient : EditorWindow
    {
        private string _prompt = "用一句话打个招呼。";
        private string _result = "（尚未运行）";
        private string _usage = "";
        private bool _isRunning;

        [MenuItem("CBIM/Demo/01_BasicChatClient")]
        private static void Open()
        {
            var w = GetWindow<Demo01_BasicChatClient>(true, "Demo 1 — 基础 ChatClient", true);
            w.minSize = new Vector2(560, 320);
        }

        private void OnGUI()
        {
            EditorGUILayout.LabelField("IChatClient 对接 OpenAI 的冒烟测试", EditorStyles.boldLabel);
            EditorGUILayout.HelpBox(
                "调用一次 IChatClient.GetResponseAsync，打印回复和 token 用量。\n" +
                "验证 Microsoft.Extensions.AI 最底层是否连通真实的 LLM 接口。",
                MessageType.Info);

            if (!ApiKeyReader.RequireKey(ApiKeyReader.OpenAIEnvVar, out var apiKey, out var err))
            {
                ApiKeyReader.DrawMissingKeyWarning(ApiKeyReader.OpenAIEnvVar, err);
                return;
            }

            EditorGUILayout.LabelField("提示词：");
            _prompt = EditorGUILayout.TextArea(_prompt, GUILayout.MinHeight(60));

            using (new EditorGUI.DisabledScope(_isRunning))
            {
                if (GUILayout.Button(_isRunning ? "发送中…" : "发送"))
                {
                    _ = RunAsync(apiKey, _prompt);
                }
            }

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("响应：", EditorStyles.boldLabel);
            EditorGUILayout.SelectableLabel(_result ?? "", EditorStyles.textArea, GUILayout.MinHeight(120));
            if (!string.IsNullOrEmpty(_usage))
            {
                EditorGUILayout.LabelField("Token 用量：", EditorStyles.boldLabel);
                EditorGUILayout.SelectableLabel(_usage, GUILayout.Height(20));
            }
        }

        private async System.Threading.Tasks.Task RunAsync(string apiKey, string prompt)
        {
            _isRunning = true;
            _result = "（发送中…）";
            _usage = "";
            Repaint();
            try
            {
                IChatClient client = DemoUtils.NewIChatClient(apiKey);
                var messages = new List<ChatMessage> { new ChatMessage(ChatRole.User, prompt) };
                ChatResponse resp = await client.GetResponseAsync(messages);

                _result = resp.Messages != null && resp.Messages.Count > 0
                    ? resp.Messages[0].Text ?? ""
                    : "（空响应）";
                if (resp.Usage != null)
                {
                    _usage = $"输入={resp.Usage.InputTokenCount}  输出={resp.Usage.OutputTokenCount}  合计={resp.Usage.TotalTokenCount}";
                }
                Debug.Log($"[Demo1] {_result}");
            }
            catch (Exception ex)
            {
                _result = "错误：" + ex.Message;
                Debug.LogException(ex);
            }
            finally
            {
                _isRunning = false;
                Repaint();
            }
        }
    }
}
